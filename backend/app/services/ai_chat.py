import json
import threading
import time
from collections.abc import Callable
from typing import TypedDict
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet
from fastapi import HTTPException
from langgraph.graph import END, START, StateGraph
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker
from pydantic import ValidationError

from ..ai_models import AIConnection, AIProposal
from ..models import Host, HostGroup
from ..repositories import ai as repository
from ..repositories import inspections
from ..schemas.ai import Detail
from ..schemas.inspections import CheckResponse, InspectionInput
from .ai_provider import MAX_TOTAL_SECONDS, ProviderError, Reply, request as model_request
from .inspection_checks import CHECK_TITLES


TOOLS = [
    {"name": "query_assets", "description": "按分组或主机名称查询资产，返回版本和地址；模糊分组匹配有歧义时请追问。",
     "parameters": {"type": "object", "properties": {"group": {"type": "string"}, "host": {"type": "string"}},
                    "additionalProperties": False}},
    {"name": "prepare_inspection", "description": "根据本会话已查询资产准备待用户确认的巡检计划，不执行。",
     "parameters": {"type": "object", "properties": {
         "name": {"type": "string"}, "host_ids": {"type": "array", "items": {"type": "integer"}},
         "checks": {"type": "array", "items": {"type": "string", "enum": list(CHECK_TITLES)}}},
         "required": ["name", "host_ids", "checks"], "additionalProperties": False}},
    {"name": "read_inspection", "description": "读取本会话已确认巡检任务的进度与结果。",
     "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}},
                    "required": ["task_id"], "additionalProperties": False}},
]
SYSTEM = ("你是运维助手。只能从工具查询到的资产准备巡检计划；分组查询歧义时先请用户澄清。"
          "巡检计划必须由用户在独立按钮确认，不能声称已执行。不要索取或展示凭据。")
MAX_ROUNDS = 4
CAPABILITY_TEST_SECONDS = 60


class GraphState(TypedDict):
    messages: list[dict]
    ledger: dict[int, dict]
    calls: list[dict]
    pending: list[dict]
    reply: Reply | None
    rounds: int
    display: str


class ChatManager:
    def __init__(self, sessions: sessionmaker[Session], cipher: Fernet):
        self.sessions, self.cipher = sessions, cipher
        self.client = httpx.Client(timeout=httpx.Timeout(20, connect=5), follow_redirects=False,
                                   limits=httpx.Limits(max_connections=8), trust_env=False)
        self.guard = threading.Lock()
        self.busy: set[str] = set()
        with sessions() as session:
            repository.interrupt_unfinished(session)

    def close(self) -> None:
        self.client.close()

    def acquire(self, session_id: str) -> None:
        with self.guard:
            if session_id in self.busy:
                raise HTTPException(409, "会话正在处理请求")
            self.busy.add(session_id)

    def release(self, session_id: str) -> None:
        with self.guard:
            self.busy.discard(session_id)

    def provider(self, record: AIConnection, messages: list[dict], tools: list[dict],
                 on_token: Callable[[str], None] | None = None, cancel: threading.Event | None = None,
                 deadline: float | None = None) -> Reply:
        key = self.cipher.decrypt(record.api_key_encrypted.encode()).decode() if record.api_key_encrypted else None
        return model_request(self.client, record.protocol, record.base_url, record.model, key, messages, tools,
                             on_token=on_token, cancel=cancel, deadline=deadline)

    def test(self, record: AIConnection) -> tuple[str, str]:
        chat = tool = "failed"
        try:
            answer = self.provider(record, [{"role": "system", "content": SYSTEM},
                                            {"role": "user", "content": "请简短回答：你好"}], [],
                                   deadline=time.monotonic() + CAPABILITY_TEST_SECONDS)
            if answer.text and not answer.calls:
                chat = "passed"
        except ProviderError:
            pass
        probe = {"name": "probe", "description": "能力探测，请调用此工具", "parameters": {
            "type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]}}
        try:
            answer = self.provider(record, [{"role": "system", "content": "必须调用 probe 工具，value 填 ok。"},
                                            {"role": "user", "content": "调用 probe(value=ok)"}], [probe],
                                   deadline=time.monotonic() + CAPABILITY_TEST_SECONDS)
            if len(answer.calls) == 1 and answer.calls[0]["name"] == "probe" and answer.calls[0]["arguments"] == {"value": "ok"}:
                tool = "passed"
        except ProviderError:
            pass
        return chat, tool

    def execute_tool(self, session_id: str, name: str, args: dict, ledger: dict[int, dict],
                     pending: list[dict]) -> dict:
        with self.sessions() as session:
            if name == "query_assets":
                if set(args) - {"group", "host"} or any(not isinstance(value, str) or len(value) > 100 for value in args.values()):
                    return {"error": "查询参数无效"}
                groups = list(session.scalars(select(HostGroup).order_by(HostGroup.id)))
                term = args.get("group", "").strip().lower()
                exact = [group for group in groups if group.name.casefold() == term] if term else []
                matches = exact or [group for group in groups if term in group.name.casefold()]
                if term and len(matches) != 1:
                    return {"error": "分组匹配不唯一或不存在", "groups": [item.name for item in matches[:20]]}
                ids = [item.id for item in matches]
                query = select(Host.id, Host.name, Host.address, Host.version, Host.group_id)
                if term:
                    query = query.where(Host.group_id.in_(ids))
                if args.get("host", "").strip():
                    needle = args["host"].strip()
                    query = query.where(or_(Host.name.contains(needle, autoescape=True),
                                            Host.address.contains(needle, autoescape=True)))
                query = query.order_by(Host.id).limit(101)
                hosts = [{"id": id, "name": host_name, "address": address, "version": version,
                          "group": next(group.name for group in groups if group.id == group_id)}
                         for id, host_name, address, version, group_id in session.execute(query)]
                if len(hosts) > 100:
                    return {"error": "查询范围过大，请缩小范围"}
                ledger.update({item["id"]: item for item in hosts})
                return {"hosts": hosts}
            if name == "prepare_inspection":
                try:
                    if set(args) != {"name", "host_ids", "checks"} or not isinstance(args["host_ids"], list) or any(
                        type(id) is not int for id in args["host_ids"]
                    ):
                        raise ValueError()
                    data = InspectionInput(name=args["name"], hosts=[{"id": id, "version": ledger[id]["version"]}
                                          for id in args["host_ids"]], checks=args["checks"])
                except (KeyError, ValueError, TypeError, ValidationError):
                    return {"error": "计划参数无效或主机未在本会话查询"}
                hosts = [{key: ledger[item.id][key] for key in ("id", "name", "address", "version")}
                         for item in data.hosts]
                proposal = {"id": str(uuid4()), "name": data.name, "hosts": hosts,
                            "checks": data.checks, "status": "pending", "task_id": None}
                pending.append(proposal)
                return {"proposal": proposal}
            if name == "read_inspection":
                if set(args) != {"task_id"} or not isinstance(args["task_id"], str):
                    return {"error": "任务参数无效"}
                associated = session.scalar(select(AIProposal.id).where(AIProposal.session_id == session_id,
                                                                          AIProposal.task_id == args["task_id"]))
                if associated is None:
                    return {"error": "任务不属于本会话"}
                task = inspections.get_task(session, args["task_id"])
                if task is None:
                    return {"error": "任务不存在"}
                result = {"id": task.id, "status": task.status, "completed_hosts": task.completed_hosts,
                        "host_count": task.host_count, "failed_hosts": task.failed_hosts,
                        "hosts": [{"name": host.host_name, "status": host.status,
                                   "checks": [{"id": check.check_id, "status": check.status,
                                               "conclusion": check.conclusion,
                                               "payload": CheckResponse.model_validate(check).payload.model_dump(mode="json")}
                                              for check in host.checks]}
                                  for host in task.hosts]}
                if len(json.dumps(result, ensure_ascii=False)) > 32_000:
                    return {"error": "结果超出对话限制，请在巡检任务详情查看"}
                return result
        return {"error": "工具未注册"}

    def send(self, session_id: str, content: str, on_token: Callable[[str], None] | None = None,
             cancel: threading.Event | None = None, deadline: float | None = None) -> Detail:
        deadline = deadline if deadline is not None else time.monotonic() + MAX_TOTAL_SECONDS
        with self.sessions() as session:
            conversation = repository.get_session(session, session_id)
            if conversation is None:
                raise HTTPException(404, "会话不存在")
            record = repository.connection(session, conversation.connection_id)
            if record is None or conversation.connection_version != record.config_version:
                raise HTTPException(409, "模型连接已修改，请新建会话")
            prior = repository.messages(session, session_id)
            history = repository.history(session, session_id)
            messages = [{"role": "system", "content": SYSTEM}]
            ledger: dict[int, dict] = {}
            intermediate = ""
            for item in prior:
                if item.status != "completed":
                    continue
                if item.role == "assistant":
                    final = item.content[len(intermediate):] if item.content.startswith(intermediate) else item.content
                    messages.append({"role": "assistant", "content": final})
                    intermediate = ""
                    continue
                messages.append({"role": "user", "content": item.content})
                turns: dict[int, list] = {}
                for entry in (entry for entry in history if entry.message_id == item.id):
                    turns.setdefault(entry.round_index, []).append(entry)
                for batch in turns.values():
                    batch.sort(key=lambda entry: entry.call_index)
                    intermediate += batch[0].assistant_text
                    messages.append({"role": "assistant", "content": batch[0].assistant_text, "tool_calls": [
                        {"id": call.call_id, "type": "function", "function": {"name": call.name,
                            "arguments": json.dumps(call.arguments)}} for call in batch]})
                    for call in batch:
                        messages.append({"role": "tool", "tool_call_id": call.call_id,
                                         "content": json.dumps(call.result, ensure_ascii=False)})
                        if call.name == "query_assets":
                            ledger.update({host["id"]: host for host in call.result.get("hosts", [])})
            user = repository.add_user(session, conversation, content)
            user_id = user.id
            messages.append({"role": "user", "content": content})
            tool_enabled = record.chat_status == "passed" and record.tool_status == "passed"
            session.expunge(record)
        state: GraphState = {"messages": messages, "ledger": ledger, "calls": [], "pending": [],
                             "reply": None, "rounds": 0, "display": ""}

        def model(state: GraphState) -> GraphState:
            if state["rounds"] >= MAX_ROUNDS:
                raise ProviderError("模型工具调用超出轮数")
            if time.monotonic() >= deadline:
                raise ProviderError("模型请求超时")
            if cancel and cancel.is_set():
                raise ProviderError("请求已取消")
            reply = self.provider(record, state["messages"], TOOLS if tool_enabled else [],
                                  on_token=on_token, cancel=cancel, deadline=deadline)
            if reply.calls and not tool_enabled:
                raise ProviderError("未授权工具调用")
            state["reply"] = reply
            state["display"] += reply.text
            state["rounds"] += 1
            return state

        def tools(state: GraphState) -> GraphState:
            reply = state["reply"]
            state["messages"].append({"role": "assistant", "content": reply.text, "tool_calls": [
                {"id": call["id"], "type": "function", "function": {"name": call["name"],
                 "arguments": json.dumps(call["arguments"])} } for call in reply.calls]})
            for index, call in enumerate(reply.calls):
                with self.sessions() as session:
                    current = repository.connection(session, record.id)
                    if current is None or current.config_version != record.config_version:
                        raise ProviderError("模型连接已修改，请新建会话")
                    if current.chat_status != "passed" or current.tool_status != "passed":
                        raise ProviderError("模型测试未通过，不能调用运维工具")
                result = self.execute_tool(session_id, call["name"], call["arguments"], state["ledger"], state["pending"])
                state["calls"].append({"call_id": call["id"], "name": call["name"],
                                        "arguments": call["arguments"], "result": result,
                                        "round_index": state["rounds"] - 1, "call_index": index,
                                        "assistant_text": reply.text})
                state["messages"].append({"role": "tool", "tool_call_id": call["id"],
                                          "content": json.dumps(result, ensure_ascii=False)})
            return state

        graph = StateGraph(GraphState)
        graph.add_node("model", model)
        graph.add_node("tools", tools)
        graph.add_edge(START, "model")
        graph.add_conditional_edges("model", lambda s: "tools" if s["reply"].calls else END)
        graph.add_edge("tools", "model")
        try:
            result = graph.compile().invoke(state, config={"recursion_limit": 12})
            if time.monotonic() >= deadline or (cancel and cancel.is_set()):
                raise ProviderError("请求已取消或超时")
            with self.sessions() as session:
                conversation = repository.get_session(session, session_id)
                current = repository.connection(session, conversation.connection_id)
                if current.config_version != conversation.connection_version:
                    raise HTTPException(409, "模型连接已修改，请新建会话")
                repository.complete(session, user_id, conversation, result["display"],
                                    result["calls"], result["pending"])
                return Detail.model_validate(conversation)
        except Exception:
            with self.sessions() as session:
                repository.finish_failure(session, user_id, "interrupted" if cancel and cancel.is_set() else "failed")
            raise
