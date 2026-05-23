from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any
from urllib import error, request

from loguru import logger

from src.config.settings import get_llm_settings

FINAL_NOTE = "以上内容仅用于纪律复盘，不构成投资建议。"


class BaseLLMClient(ABC):
    @abstractmethod
    def complete(self, system: str, user: str) -> dict[str, Any]:
        raise NotImplementedError


class MockLLMClient(BaseLLMClient):
    provider = "mock"
    model = "mock-v1"

    def complete(self, system: str, user: str) -> dict[str, Any]:
        payload = self._build_payload(user)
        text = json.dumps(payload, ensure_ascii=False)
        return {
            "text": text,
            "model": self.model,
            "provider": self.provider,
            "status": "success",
            "error_message": "",
        }

    def _build_payload(self, user: str) -> dict[str, Any]:
        is_weekly = "统计区间" in user
        total_count = _extract_int(user, r"交易次数：(\d+)")
        not_rule_based = _extract_int(user, r"不符合规则(?:交易|次数)：(\d+)")
        chasing = _extract_int(user, r"追涨次数：(\d+)")
        panic = _extract_int(user, r"恐慌次数：(\d+)")
        temporary = _extract_int(user, r"临时决策次数：(\d+)")
        compliance = _extract_float(user, r"纪律执行率：([\d.]+)%")

        behavior_findings: list[str] = []
        if not_rule_based > 0:
            behavior_findings.append(f"存在 {not_rule_based} 笔不符合规则的交易，需关注执行偏差。")
        if chasing > 0:
            behavior_findings.append(f"出现 {chasing} 次追涨情绪记录。")
        if panic > 0:
            behavior_findings.append(f"出现 {panic} 次恐慌情绪记录。")
        if temporary > 0:
            behavior_findings.append(f"出现 {temporary} 次临时决策记录。")
        if not behavior_findings:
            behavior_findings.append("暂未发现明显异常行为模式。")

        risk_summary = _extract_alerts(user)
        if not risk_summary:
            risk_summary = ["当前未发现额外仓位风险提醒。"]

        if is_weekly:
            discipline_summary = (
                f"本周共 {total_count} 笔交易，纪律执行率约 {compliance:.1f}%。"
                if compliance
                else f"本周共 {total_count} 笔交易，请继续保持计划内执行。"
            )
            action_suggestion = [
                "下周优先复盘不符合规则的交易原因。",
                "保持现金缓冲，避免情绪化操作。",
                "继续对照策略信号检查执行偏差。",
            ]
        else:
            discipline_summary = (
                f"当日共 {total_count} 笔交易，其中 {not_rule_based} 笔不符合规则。"
                if total_count
                else "当日无交易记录，保持观察即可。"
            )
            action_suggestion = [
                "下个交易日继续对照策略信号检查执行偏差。",
                "避免追涨与临时决策。",
                "关注仓位提醒并保持现金缓冲。",
            ]

        return {
            "discipline_summary": discipline_summary,
            "behavior_findings": behavior_findings[:3],
            "risk_summary": risk_summary[:3],
            "action_suggestion": action_suggestion[:3],
            "final_note": FINAL_NOTE,
        }


class OpenAICompatibleClient(BaseLLMClient):
    provider = "openai_compatible"

    def __init__(self, api_key: str, api_base: str, model: str, timeout: int = 30) -> None:
        if not api_key:
            raise ValueError("LLM_API_KEY is required for openai_compatible provider")
        if not api_base:
            raise ValueError("LLM_API_BASE is required for openai_compatible provider")
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.model = model or "gpt-4o-mini"
        self.timeout = timeout

    def complete(self, system: str, user: str) -> dict[str, Any]:
        url = f"{self.api_base}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            text = body["choices"][0]["message"]["content"]
            return {
                "text": text,
                "model": self.model,
                "provider": self.provider,
                "status": "success",
                "error_message": "",
            }
        except (error.URLError, error.HTTPError, KeyError, json.JSONDecodeError, TimeoutError) as exc:
            return {
                "text": "",
                "model": self.model,
                "provider": self.provider,
                "status": "failed",
                "error_message": str(exc),
            }


def get_llm_client(settings: dict[str, Any] | None = None, *, force_mock: bool = False) -> BaseLLMClient:
    cfg = settings or get_llm_settings()
    if force_mock or cfg.get("provider") in ("", "mock"):
        return MockLLMClient()
    if cfg.get("provider") == "openai_compatible":
        try:
            return OpenAICompatibleClient(
                api_key=str(cfg.get("api_key") or ""),
                api_base=str(cfg.get("api_base") or ""),
                model=str(cfg.get("model") or ""),
                timeout=int(cfg.get("timeout") or 30),
            )
        except ValueError as exc:
            logger.warning("LLM client fallback to mock: {}", exc)
            return MockLLMClient()
    logger.warning("Unknown LLM provider {}, fallback to mock", cfg.get("provider"))
    return MockLLMClient()


def _extract_int(text: str, pattern: str) -> int:
    match = re.search(pattern, text)
    return int(match.group(1)) if match else 0


def _extract_float(text: str, pattern: str) -> float:
    match = re.search(pattern, text)
    return float(match.group(1)) if match else 0.0


def _extract_alerts(text: str) -> list[str]:
    match = re.search(r"仓位提醒：(\[.*?\]|'.*?')", text)
    if not match:
        return []
    raw = match.group(1)
    try:
        parsed = json.loads(raw.replace("'", '"'))
        if isinstance(parsed, list):
            return [str(item) for item in parsed[:3]]
    except json.JSONDecodeError:
        pass
    return [raw[:120]]
