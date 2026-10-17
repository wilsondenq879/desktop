"""
title: Skill 語意自動路由
description: 依照最新訊息的語意，自動載入少量最相關的 Open WebUI Skills；手動選擇永遠優先。
version: 1.1.0
"""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field


class Filter:
    """Resolve skills before model execution instead of relying on tool calling."""

    class Valves(BaseModel):
        priority: int = Field(default=-100, description="在其他全域 Filter 前先完成 Skill 路由。")
        enabled: bool = Field(default=True, description="啟用 Skill 語意自動路由。")
        max_skills: int = Field(default=2, ge=1, le=3, description="單次最多自動載入的 Skills 數量。")
        min_score: float = Field(default=0.90, ge=0.0, le=1.5, description="語意與關鍵詞混合分數門檻。")
        show_status: bool = Field(default=True, description="在對話中顯示已自動使用的 Skills。")

    class UserValves(BaseModel):
        mode: Literal["auto", "suggest", "manual"] = Field(
            default="auto",
            description="auto 自動載入；suggest 僅顯示建議；manual 只接受手動選擇。",
        )

    _MANUAL_MENTION = re.compile(r"<(?:\$[a-z0-9_-]+(?:\|[^>]*)?|/[a-z0-9_-]+\|[^>]*)>", re.I)
    _FIREWORKS_SKILL_ID = "fireworks-tech-graph"
    _FIREWORKS_TOOL_ID = "openwebui_fireworks_renderer"
    _RESEARCH_SKILL_ID = "lmlab-source-grounded-research"
    _RESEARCH_TERMS = (
        "最新", "目前", "已上市", "上市", "在售", "販售", "銷售", "發布", "發表",
        "價格", "規格", "相容", "版本", "研究", "查證", "來源", "引用", "分析",
    )
    _CARD_TERMS = ("知識卡", "知識卡片", "社群卡", "教育卡", "插畫卡")
    _ROUTER_TERMS = ("路由器", "網通", "無線網路", "wifi", "wi-fi", "switch", "交換器")
    _WORD = re.compile(r"[a-z0-9][a-z0-9_+.-]{1,}|[\u3400-\u9fff]+", re.I)
    _STOP = {
        "可以", "幫我", "請問", "一下", "我要", "需要", "使用", "這個", "那個", "怎麼", "如何",
        "什麼", "是否", "以及", "還有", "一個", "目前", "後續", "直接", "the", "and", "for",
        "with", "from", "this", "that", "please", "help", "use", "using", "make", "create", "給我",
        "畫一張", "做一個", "產出一個", "協助我",
    }
    _EXPANSIONS = (
        (("市場", "競品", "競爭對手", "競爭分析"), "market competitor competitive analysis landscape research 競品分析 市場研究"),
        (("研究", "查證", "資料來源", "引用"), "research sources evidence citations web search 研究 查證 來源"),
        (("架構", "拓撲", "rdma", "roce", "交換器", "連線圖"), "technical architecture topology diagram network hardware 技術架構 網路拓撲"),
        (("網頁", "網站", "react", "前端", "ui", "ux"), "website web react frontend interface design 網頁 前端 介面設計"),
        (("圖片", "插畫", "照片", "海報", "生成圖"), "image generation illustration photo poster 圖片生成 插畫"),
        (("影片", "短片", "youtube", "動畫"), "video animation youtube shorts motion 影片 動畫"),
        (("簡報", "投影片", "ppt", "pptx"), "presentation slides deck powerpoint 簡報 投影片"),
        (("路由器", "網通", "無線網路", "wifi", "switch"), "router networking wireless wifi switch 路由器 網通"),
    )

    def __init__(self):
        self.valves = self.Valves()
        self._cache_signature = None
        self._cache_vectors = None

    @staticmethod
    def _message_text(value) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return "\n".join(
                str(part.get("text", ""))
                for part in value
                if isinstance(part, dict) and part.get("type") in (None, "text")
            )
        return ""

    @classmethod
    def _latest_user(cls, messages: list[dict]):
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("role") == "user":
                return message, cls._message_text(message.get("content"))
        return None, ""

    @classmethod
    def _tokens(cls, value: str) -> set[str]:
        normalized = unicodedata.normalize("NFKC", value or "").lower()
        for phrase in sorted(cls._STOP, key=len, reverse=True):
            normalized = normalized.replace(phrase, " ")
        tokens: set[str] = set()
        for match in cls._WORD.findall(normalized):
            if match in cls._STOP:
                continue
            if re.fullmatch(r"[\u3400-\u9fff]+", match):
                if 2 <= len(match) <= 8:
                    tokens.add(match)
                for size in (2, 3):
                    for index in range(0, max(0, len(match) - size + 1)):
                        token = match[index : index + size]
                        if token not in cls._STOP:
                            tokens.add(token)
            elif len(match) >= 2:
                tokens.add(match)
        return tokens

    @classmethod
    def _expand_query(cls, query: str) -> str:
        lowered = unicodedata.normalize("NFKC", query or "").lower()
        additions = [expansion for triggers, expansion in cls._EXPANSIONS if any(trigger in lowered for trigger in triggers)]
        return " ".join([query, *additions])

    @staticmethod
    def _intent_boost(query: str, skill_id: str) -> float:
        lowered = unicodedata.normalize("NFKC", query or "").lower()
        boost = 0.0
        is_router = any(term in lowered for term in Filter._ROUTER_TERMS)
        is_current_or_research = any(term in lowered for term in Filter._RESEARCH_TERMS)
        is_card_request = any(term in lowered for term in Filter._CARD_TERMS)

        # Product, availability and market questions need source-grounded
        # research.  Do not let an embedding-only match route these requests
        # into a creative card/video skill (which adds several thousand prompt
        # characters without helping the answer).
        if is_router and (is_current_or_research or "哪些" in lowered or "何時" in lowered):
            boost += {
                Filter._RESEARCH_SKILL_ID: 0.42,
                "deep-research": 0.16,
                "consulting-analysis": 0.06,
            }.get(skill_id, 0.0)
            if not is_card_request and skill_id in {
                "wilsonspeak-knowledge-cards",
                "asusrouter-app-tutorial-skill",
                "faceless-explainer",
            }:
                boost -= 0.35
        if any(term in lowered for term in ("市場", "競品", "競爭對手", "競爭分析")):
            boost += {
                "competitor-analysis": 0.30,
                "consulting-analysis": 0.18,
                "deep-research": 0.10,
                Filter._RESEARCH_SKILL_ID: 0.24,
                "market-segments": 0.08,
                "market-sizing": 0.08,
            }.get(skill_id, 0.0)
        if any(term in lowered for term in ("架構", "拓撲", "rdma", "roce", "連線圖")):
            boost += {
                "fireworks-tech-graph": 0.42,
                # Keep the inline React renderer as a low-priority fallback for
                # sessions that do not expose Desktop's file/terminal tools.
                "technical-architecture-diagram": 0.06,
            }.get(skill_id, 0.0)
        if any(term in lowered for term in ("網頁", "網站", "react", "前端")):
            boost += {
                "lmlab-web-design-engineer": 0.16,
                "lmlab-node-web-engineering": 0.14,
                "web-design-engineer": 0.16,
            }.get(skill_id, 0.0)
        return boost

    @staticmethod
    def _descriptor(skill) -> str:
        content = skill.content or ""
        trigger = ""
        match = re.search(
            r"(?ims)^##\s+(?:when to use|何時使用|使用時機|觸發條件)\s*$\s*(.*?)(?=^##\s+|\Z)",
            content,
        )
        if match:
            trigger = match.group(1).strip()[:900]
        meta = skill.meta or {}
        tags = " ".join(str(tag) for tag in (meta.get("tags") or [])) if isinstance(meta, dict) else ""
        return "。".join(part for part in (skill.id, skill.name, skill.description or "", tags, trigger) if part)

    @staticmethod
    def _cosine(left, right) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(float(a) * float(b) for a, b in zip(left, right))
        left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
        right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0

    @staticmethod
    def _append_hidden_mentions(message: dict, skill_ids: list[str]) -> None:
        suffix = " ".join(f"</{skill_id}|>" for skill_id in skill_ids)
        content = message.get("content")
        if isinstance(content, str):
            message["content"] = f"{content.rstrip()}\n{suffix}"
            return
        if isinstance(content, list):
            for part in reversed(content):
                if isinstance(part, dict) and part.get("type") in (None, "text"):
                    part["text"] = f"{str(part.get('text', '')).rstrip()}\n{suffix}"
                    return
            content.append({"type": "text", "text": suffix})

    async def _rank(self, query: str, skills: list, request, user) -> list[dict]:
        expanded_query = self._expand_query(query)
        descriptors = [self._descriptor(skill) for skill in skills]
        query_tokens = self._tokens(expanded_query)
        descriptor_tokens = [self._tokens(value) for value in descriptors]
        embedding_function = getattr(request.app.state, "EMBEDDING_FUNCTION", None) if request else None
        query_vector = None
        document_vectors = None

        if embedding_function:
            try:
                if user:
                    from open_webui.models.users import UserModel

                    user_model = UserModel(**user)
                else:
                    user_model = None
                signature = tuple((skill.id, skill.updated_at, descriptors[index]) for index, skill in enumerate(skills))
                query_vector = await embedding_function(f"query: {expanded_query[:1600]}", user=user_model)
                if self._cache_signature == signature and self._cache_vectors is not None:
                    document_vectors = self._cache_vectors
                else:
                    document_vectors = await embedding_function(
                        [f"passage: {descriptor[:1600]}" for descriptor in descriptors],
                        user=user_model,
                    )
                    self._cache_signature = signature
                    self._cache_vectors = document_vectors
            except Exception:
                query_vector = None
                document_vectors = None

        ranked = []
        normalized_query = unicodedata.normalize("NFKC", query).lower()
        for index, skill in enumerate(skills):
            overlap = query_tokens & descriptor_tokens[index]
            lexical = len(overlap) / max(4, min(12, len(query_tokens)))
            semantic = self._cosine(query_vector, document_vectors[index]) if query_vector and document_vectors else 0.0
            normalized_name = unicodedata.normalize("NFKC", skill.name or "").lower().strip()
            exact = 0.30 if normalized_name and normalized_name in normalized_query else 0.0
            intent = self._intent_boost(query, skill.id)
            score = semantic + min(0.16, lexical * 0.28) + exact + intent
            ranked.append(
                {
                    "skill": skill,
                    "score": score,
                    "semantic": semantic,
                    "lexical": lexical,
                    "intent": intent,
                    "overlap": sorted(overlap),
                }
            )
        return sorted(ranked, key=lambda item: (item["score"], item["lexical"]), reverse=True)

    async def inlet(
        self,
        body: dict,
        __request__=None,
        __user__: dict | None = None,
        __event_emitter__=None,
    ) -> dict:
        if not self.valves.enabled:
            return body

        messages = body.get("messages")
        if not isinstance(messages, list):
            return body
        user_message, query = self._latest_user(messages)
        if not user_message or len(query.strip()) < 4:
            return body

        # Explicit picker selection or an existing skill id is authoritative.
        if body.get("skill_ids") or self._MANUAL_MENTION.search(query):
            return body

        user_valves = (__user__ or {}).get("valves") or {}
        if hasattr(user_valves, "model_dump"):
            user_valves = user_valves.model_dump()
        mode = user_valves.get("mode", "auto")
        if mode == "manual":
            return body

        try:
            from open_webui.models.skills import Skills

            skills = [
                skill
                for skill in await Skills.get_skills(user_id=(__user__ or {}).get("id"))
                if skill.is_active and (skill.description or "").strip()
            ]
            if not skills:
                return body

            ranked = await self._rank(query, skills, __request__, __user__ or {})
            if not ranked:
                return body
            top = ranked[0]
            # Explicit high-confidence intent mappings must still work when the
            # embedding backend is temporarily asleep or unavailable. The high
            # 0.30 cutoff is reserved for narrow mappings such as architecture
            # -> Fireworks and competitor research -> competitor-analysis.
            hard_intent = top["intent"] >= 0.30 and top["lexical"] >= 0.08
            has_signal = hard_intent or (
                top["score"] >= self.valves.min_score
                and (top["lexical"] >= 0.08 or top["semantic"] >= 0.925)
            )
            if not has_signal:
                return body

            selected = [top]
            for candidate in ranked[1:]:
                if len(selected) >= self.valves.max_skills:
                    break
                if (
                    candidate["score"] >= self.valves.min_score
                    and top["score"] - candidate["score"] <= 0.055
                    and candidate["lexical"] >= 0.12
                ):
                    selected.append(candidate)

            names = [item["skill"].name for item in selected]
            skill_ids = [item["skill"].id for item in selected]
            if self.valves.show_status and __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": (
                                "建議使用 Skill：" if mode == "suggest" else "已自動使用 Skill："
                            )
                            + "、".join(names),
                            "done": True,
                        },
                    }
                )

            metadata = body.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
                body["metadata"] = metadata
            metadata["semantic_skill_router"] = {
                "mode": mode,
                "skill_ids": skill_ids,
                "scores": {item["skill"].id: round(item["score"], 4) for item in selected},
            }
            if mode == "suggest":
                return body

            body["skill_ids"] = sorted(set(body.get("skill_ids") or []) | set(skill_ids))
            # Fireworks is not a prompt-only skill. Give native-capable models
            # the renderer in the same turn so they return a real SVG artifact
            # rather than falling back to the old inline JSON card protocol.
            if self._FIREWORKS_SKILL_ID in skill_ids:
                body["tool_ids"] = sorted(set(body.get("tool_ids") or []) | {self._FIREWORKS_TOOL_ID})
                params = body.get("params")
                if not isinstance(params, dict):
                    params = {}
                    body["params"] = params
                params.setdefault("function_calling", "native")
            self._append_hidden_mentions(user_message, skill_ids)
        except Exception:
            # Routing must never prevent the user's original message from running.
            return body

        return body
