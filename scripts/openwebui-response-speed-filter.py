"""
title: 回答生成速度
description: 每則回答附上實際 token/s；優先使用模型解碼統計，不把繪圖時間混為推論速度。
version: 1.1.0
"""
import math
import re
import time
import uuid
from pydantic import BaseModel, Field


class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=1000, description="在繪圖與術語校正之後加入速度資訊")

    def __init__(self):
        self.valves = self.Valves()

    @staticmethod
    def _number(value):
        if isinstance(value, bool):
            return None
        try:
            number = float(value)
            return number if math.isfinite(number) and number > 0 else None
        except (ValueError, TypeError):
            return None

    @classmethod
    def _measurement(cls, usage):
        if not isinstance(usage, dict):
            return None
        # Ollama durations are nanoseconds. eval_count is the count for that
        # same decode, unlike middleware's cumulative output_tokens.
        count, duration = cls._number(usage.get("eval_count")), cls._number(usage.get("eval_duration"))
        if count and duration:
            return {"tokens":count, "seconds":duration/1e9}
        # llama.cpp timings are milliseconds, not nanoseconds.
        count, duration = cls._number(usage.get("predicted_n")), cls._number(usage.get("predicted_ms"))
        if count and duration:
            return {"tokens":count, "seconds":duration/1000}
        speed = cls._number(usage.get("response_token/s")) or cls._number(usage.get("predicted_per_second"))
        if speed:
            count = cls._number(usage.get("eval_count")) or cls._number(usage.get("predicted_n")) or cls._number(usage.get("completion_tokens")) or cls._number(usage.get("output_tokens"))
            return {"tokens":count, "seconds":count/speed} if count else {"speed":speed}
        return None

    @staticmethod
    def _state(request):
        return getattr(request.state, "response_speed", None) if request is not None else None

    def inlet(self, body: dict, __request__=None, __metadata__=None) -> dict:
        if (__metadata__ or {}).get("task") or (body.get("metadata") or {}).get("task"):
            return body  # Do not append metrics to JSON title/search helper jobs.
        if __request__ is not None:
            diagram = getattr(__request__.state, "fireworks_diagram", None) or {}
            calls = {}
            measurement = self._measurement(diagram.get("preface_usage"))
            if measurement:
                calls["architecture-preface"] = measurement
            __request__.state.response_speed = {"started":diagram.get("started", time.monotonic()), "calls":calls}
        return body

    def stream(self, event: dict, __request__=None) -> dict:
        state = self._state(__request__)
        if state is None:
            return event
        usage = dict(event.get("usage") or {})
        usage.update(event.get("timings") or {})
        if isinstance(event.get("response"), dict):
            usage.update(event["response"].get("usage") or {})
        measurement = self._measurement(usage)
        if measurement:
            # A stream may repeat cumulative usage. Replace the snapshot for
            # the same completion ID instead of counting it twice.
            key = event.get("id") or str((usage.get("eval_count"), usage.get("eval_duration"), usage.get("predicted_n"), usage.get("predicted_ms"), usage.get("response_token/s")))
            state["calls"][key] = measurement
        return event

    @classmethod
    def _footer(cls, state, usage, elapsed):
        calls = list((state or {}).get("calls", {}).values())
        calls.extend(m for usage in (state or {}).get("extra_usage", []) if (m := cls._measurement(usage)))
        if not calls:
            measurement = cls._measurement(usage)
            calls = [measurement] if measurement else []
        measured = [c for c in calls if c.get("tokens") and c.get("seconds")]
        if measured and len(measured) == len(calls):
            speed = sum(c["tokens"] for c in measured)/sum(c["seconds"] for c in measured)
            return f"{speed:.1f} tokens/s"
        if calls and calls[-1].get("speed"):
            return f"{calls[-1]['speed']:.1f} tokens/s"
        # Standard OpenAI usage has token counts but no decode duration. Use
        # real token counts, never characters/words, and label wall time clearly.
        count = cls._number(usage.get("output_tokens")) or cls._number(usage.get("completion_tokens"))
        if count and elapsed and elapsed > 0:
            return f"≈ {count/elapsed:.1f} tokens/s"
        return "N/A tokens/s"

    @staticmethod
    def _strip_footer(text):
        text = re.sub(r"\n*<!-- openwebui-response-speed -->[\s\S]*?<!-- /openwebui-response-speed -->", "", text).rstrip()
        # Only remove a standalone final footer, never interior speed data.
        return re.sub(r"\n\n(?:≈ )?(?:\d+(?:\.\d+)?|N/A) tokens/s\s*\Z", "", text).rstrip()

    def outlet(self, body: dict, __request__=None, __metadata__=None) -> dict:
        if (__metadata__ or {}).get("task") or (body.get("metadata") or {}).get("task"):
            return body
        target_id = body.get("id")
        assistant = next((m for m in reversed(body.get("messages", [])) if m.get("role") == "assistant" and (not target_id or m.get("id") in (None, target_id))), None)
        if assistant is None:
            return body
        state = self._state(__request__) or {}
        elapsed = time.monotonic()-state["started"] if "started" in state else None
        footer = "\n\n"+self._footer(state, assistant.get("usage") or {}, elapsed)
        output = assistant.get("output") or []
        # Preserve tool history, citations and existing message IDs. Only the
        # last assistant text part receives the footer; both formats persist.
        parts = [p for item in output if item.get("type") == "message" for p in item.get("content", []) if p.get("type") == "output_text"]
        content = assistant.get("content")
        if not isinstance(content, str):
            content = "".join(str(p.get("text", "")) for p in parts)
        assistant["content"] = self._strip_footer(content)+footer
        if parts:
            for part in parts:
                part["text"] = self._strip_footer(str(part.get("text", "")))
            parts[-1]["text"] += footer
        else:
            output.append({"id":"msg_"+uuid.uuid4().hex,"type":"message","role":"assistant","status":"completed","content":[{"type":"output_text","text":assistant["content"]}]})
        assistant["output"] = output
        return body
