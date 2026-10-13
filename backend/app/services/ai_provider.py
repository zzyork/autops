import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx


MAX_RESPONSE = 256_000
MAX_TEXT = 16_000
MAX_RESPONSE_BUDGET = 2 * 1024 * 1024
MAX_TEXT_BUDGET = 65_536
MAX_CALLS = 4
MAX_CONTEXT = 128_000
MAX_TOTAL_SECONDS = 300
DEFAULT_READ_TIMEOUT_SECONDS = 20
MAX_READ_TIMEOUT_SECONDS = 60


class ProviderError(Exception):
    pass


@dataclass
class Reply:
    text: str
    calls: list[dict]


def request(client: httpx.Client, protocol: str, base_url: str, model: str,
            api_key: str | None, messages: list[dict], tools: list[dict],
            on_token: Callable[[str], None] | None = None, cancel: threading.Event | None = None,
             deadline: float | None = None, max_tokens: int = 1024,
              max_text: int = MAX_TEXT, max_response: int = MAX_RESPONSE,
              read_timeout_seconds: int = DEFAULT_READ_TIMEOUT_SECONDS) -> Reply:
    if type(max_tokens) is not int or not 1 <= max_tokens <= 8192:
        raise ProviderError("模型输出限额无效")
    if (type(max_text) is not int or not 1 <= max_text <= MAX_TEXT_BUDGET
            or type(max_response) is not int or not 1 <= max_response <= MAX_RESPONSE_BUDGET):
        raise ProviderError("模型响应限额无效")
    if type(read_timeout_seconds) is not int or not 1 <= read_timeout_seconds <= MAX_READ_TIMEOUT_SECONDS:
        raise ProviderError("模型读取时限无效")
    if protocol == "openai_compatible":
        url = base_url + "/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        body = {"model": model, "messages": messages, "max_tokens": max_tokens, "stream": True}
        if tools:
            body["tools"] = [{"type": "function", "function": item} for item in tools]
    else:
        url = base_url + ("/messages" if base_url.endswith("/v1") else "/v1/messages")
        headers = {"anthropic-version": "2023-06-01"}
        if api_key:
            headers["x-api-key"] = api_key
        converted = []
        for message in messages:
            role = message["role"]
            if role == "system":
                continue
            if role == "tool":
                block = {"type": "tool_result", "tool_use_id": message["tool_call_id"], "content": message["content"]}
                if converted and converted[-1]["role"] == "user" and isinstance(converted[-1]["content"], list):
                    converted[-1]["content"].append(block)
                else:
                    converted.append({"role": "user", "content": [block]})
            elif role == "assistant" and message.get("tool_calls"):
                content = ([{"type": "text", "text": message["content"]}] if message.get("content") else [])
                content.extend({"type": "tool_use", "id": call["id"], "name": call["function"]["name"],
                                "input": json.loads(call["function"]["arguments"])} for call in message["tool_calls"])
                converted.append({"role": "assistant", "content": content})
            else:
                converted.append({"role": role, "content": message["content"]})
        body = {"model": model, "max_tokens": max_tokens, "system": messages[0]["content"],
                "messages": converted, "stream": True}
        if tools:
            body["tools"] = [{"name": item["name"], "description": item["description"],
                               "input_schema": item["parameters"]} for item in tools]
    if len(json.dumps(body, ensure_ascii=False)) > MAX_CONTEXT:
        raise ProviderError("会话内容超出限制")
    deadline = deadline if deadline is not None else time.monotonic() + MAX_TOTAL_SECONDS
    text_parts: list[str] = []
    text_length = 0
    calls: dict[int, dict] = {}
    finish: str | None = None
    stopped = False

    def append_text(fragment: str) -> None:
        nonlocal text_length
        if not isinstance(fragment, str):
            raise ProviderError("模型响应格式无效")
        text_length += len(fragment)
        if text_length > max_text:
            raise ProviderError(f"模型响应文本超出限制（{text_length}/{max_text} 字符）")
        text_parts.append(fragment)
        if fragment and on_token is not None:
            on_token(fragment)

    def check() -> None:
        if cancel is not None and cancel.is_set():
            raise ProviderError("请求已取消")
        if time.monotonic() >= deadline:
            raise ProviderError("模型请求超时")

    def consume(event: str, data: str) -> None:
        nonlocal finish, stopped
        if event == "error":
            raise ProviderError("模型请求失败")
        if protocol == "openai_compatible" and data == "[DONE]":
            stopped = True
            return
        if not data:
            return
        payload = json.loads(data)
        if protocol == "openai_compatible":
            if not payload.get("choices"):
                return
            choice = payload["choices"][0]
            delta = choice.get("delta") or {}
            if delta.get("content") is not None:
                append_text(delta["content"])
            for call in delta.get("tool_calls") or []:
                index = call["index"]
                if type(index) is not int or index < 0 or index >= MAX_CALLS:
                    raise ProviderError("模型工具调用超出限制")
                item = calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                item["id"] += call.get("id") or ""
                function = call.get("function") or {}
                item["name"] += function.get("name") or ""
                item["arguments"] += function.get("arguments") or ""
                if len(item["arguments"]) > 8192:
                    raise ProviderError("模型工具参数超出限制")
            if choice.get("finish_reason") is not None:
                finish = choice["finish_reason"]
        elif event == "content_block_start":
            index = payload["index"]
            block = payload["content_block"]
            if type(index) is not int or index < 0 or index > MAX_CALLS + 8:
                raise ProviderError("模型响应格式无效")
            if block["type"] == "tool_use":
                if len(calls) >= MAX_CALLS:
                    raise ProviderError("模型工具调用超出限制")
                calls[index] = {"id": block["id"], "name": block["name"],
                                "arguments": "", "initial": block.get("input", {})}
            elif block["type"] == "text":
                append_text(block.get("text", ""))
        elif event == "content_block_delta":
            delta = payload["delta"]
            if delta["type"] == "text_delta":
                append_text(delta["text"])
            elif delta["type"] == "input_json_delta":
                item = calls[payload["index"]]
                item["arguments"] += delta["partial_json"]
                if len(item["arguments"]) > 8192:
                    raise ProviderError("模型工具参数超出限制")
        elif event == "message_delta":
            finish = payload["delta"].get("stop_reason")
        elif event == "message_stop":
            stopped = True

    try:
        check()
        remaining = deadline - time.monotonic()
        timeout = httpx.Timeout(min(DEFAULT_READ_TIMEOUT_SECONDS, remaining), connect=min(5, remaining),
                                read=min(read_timeout_seconds, remaining))
        with client.stream("POST", url, headers=headers, json=body, follow_redirects=False,
                           timeout=timeout) as response:
            if response.status_code != 200:
                raise ProviderError(f"模型请求失败（HTTP {response.status_code}）")
            event_name = ""
            data_lines: list[str] = []
            total_bytes = 0
            buffer = bytearray()

            def read_line(line: str) -> None:
                nonlocal event_name, data_lines
                if not line:
                    if data_lines:
                        consume(event_name, "\n".join(data_lines))
                    event_name, data_lines = "", []
                elif line.startswith("event:"):
                    event_name = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].lstrip(" "))
                elif not line.startswith((":", "id:", "retry:")):
                    raise ProviderError("模型响应格式无效")

            for chunk in response.iter_bytes():
                check()
                total_bytes += len(chunk)
                if total_bytes > max_response:
                    raise ProviderError(f"模型流式响应超出限制（{total_bytes}/{max_response} 字节）")
                buffer.extend(chunk)
                while b"\n" in buffer:
                    raw, _, buffer = buffer.partition(b"\n")
                    read_line(raw.removesuffix(b"\r").decode("utf-8"))
                    if stopped:
                        break
                if stopped:
                    break
            if buffer:
                read_line(bytes(buffer).removesuffix(b"\r").decode("utf-8"))
            if data_lines and not stopped:
                consume(event_name, "\n".join(data_lines))
        check()
        valid_finishes = ("stop", "tool_calls") if protocol == "openai_compatible" else ("end_turn", "tool_use")
        if not stopped or finish not in valid_finishes:
            if finish in ("length", "max_tokens"):
                raise ProviderError("模型响应未完成（达到输出 token 限额）")
            if finish == "content_filter":
                raise ProviderError("模型响应未完成（内容过滤）")
            if not stopped:
                raise ProviderError("模型响应未完成（缺少流结束标记）")
            raise ProviderError("模型响应未完成")
        parsed = []
        for item in (calls[index] for index in sorted(calls)):
            arguments = json.loads(item["arguments"]) if item["arguments"] else item.get("initial", {})
            if not isinstance(arguments, dict) or not item["id"] or len(item["id"]) > 200 or not item["name"] or len(item["name"]) > 80:
                raise ProviderError("模型工具参数无效")
            parsed.append({"id": item["id"], "name": item["name"], "arguments": arguments})
        result = Reply("".join(text_parts), parsed)
        if (not result.text and not result.calls) or len({call["id"] for call in parsed}) != len(parsed):
            raise ProviderError("模型响应格式无效")
        return result
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, UnicodeError) as exc:
        # 异常原文可能带有 URL 或响应内容，只保留类型供服务端诊断。
        raise ProviderError(f"模型请求或响应无效（{type(exc).__name__}）") from exc
