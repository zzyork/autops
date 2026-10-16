import asyncio
import json
import logging
import threading
import time
from collections import Counter
from collections.abc import Callable

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

from ..repositories import operations as repository
from ..schemas.operations import EventSnapshot

logger = logging.getLogger(__name__)
MAX_SUBSCRIPTIONS = 32
MAX_PER_TASK = 4
POLL_SECONDS = 0.5
HEARTBEAT_SECONDS = 15
FINISHED = {"succeeded", "failed", "partial", "unknown", "interrupted", "expired"}


class _SubscriptionResponse(StreamingResponse):
    def __init__(self, content, release: Callable[[], None], **kwargs):
        super().__init__(content, **kwargs)
        self.release = release

    async def __call__(self, scope, receive, send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            try:
                await self.body_iterator.aclose()
            finally:
                self.release()


class OperationStreams:
    def __init__(self, sessions):
        self.sessions = sessions
        self.lock = threading.Lock()
        self.closed = threading.Event()
        self.subscriptions: Counter[str] = Counter()

    def close(self) -> None:
        with self.lock:
            self.closed.set()
            self.subscriptions.clear()

    def subscribe(self, task_id: str, host_id: int | None) -> StreamingResponse:
        with self.lock:
            if self.closed.is_set() or sum(self.subscriptions.values()) >= MAX_SUBSCRIPTIONS or (
                    self.subscriptions[task_id] >= MAX_PER_TASK):
                raise HTTPException(503, "实时查看连接数已满")
            self.subscriptions[task_id] += 1
        released = False

        def release_once() -> None:
            nonlocal released
            with self.lock:
                if released:
                    return
                released = True
                if self.subscriptions[task_id] > 0:
                    self.subscriptions[task_id] -= 1
                    if not self.subscriptions[task_id]:
                        del self.subscriptions[task_id]

        try:
            def read_snapshot() -> EventSnapshot | None:
                with self.sessions() as session:
                    # SQLite's deferred driver BEGIN does not pin a read snapshot across SELECTs.
                    session.connection().exec_driver_sql("BEGIN")
                    value = repository.event_snapshot(session, task_id, host_id)
                    return EventSnapshot.model_validate(value) if value is not None else None

            initial = read_snapshot()
            if initial is None:
                raise HTTPException(404, "运维任务或任务主机不存在")

            def event(name: str, snapshot: EventSnapshot) -> bytes:
                data = json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
                return f"event: {name}\ndata: {data}\n\n".encode("utf-8")

            async def stream():
                try:
                    if self.closed.is_set():
                        return
                    previous = initial
                    yield event("snapshot", previous)
                    if previous.status in FINISHED:
                        yield event("done", previous)
                        return
                    heartbeat = time.monotonic()
                    while not self.closed.is_set():
                        await asyncio.sleep(POLL_SECONDS)
                        if self.closed.is_set():
                            break
                        current = await run_in_threadpool(read_snapshot)
                        if current is None:
                            raise ValueError("任务已不存在")
                        if current != previous:
                            previous = current
                            yield event("snapshot", current)
                        if current.status in FINISHED:
                            yield event("done", current)
                            return
                        if time.monotonic() - heartbeat >= HEARTBEAT_SECONDS:
                            yield b": heartbeat\n\n"
                            heartbeat = time.monotonic()
                except Exception as exc:
                    logger.warning("Operation stream %s read failed: %s", task_id, type(exc).__name__)
                    yield b"event: error\ndata: {}\n\n"
                finally:
                    release_once()

            return _SubscriptionResponse(stream(), release_once, media_type="text/event-stream",
                                         background=BackgroundTask(release_once),
                                         headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
        except BaseException:
            release_once()
            raise
