"""DeepSeek-R1-Distill client via vLLM/Ollama with fallback."""

from __future__ import annotations

import os
from typing import Any

import httpx

from nlp.sanitizer import sanitize_response


class DeepSeekUnavailableError(Exception):
    pass


async def generate_guidance(
    *,
    topic: str,
    language: str = "en",
    accounting_standard: str = "CAS",
) -> str:
    if os.getenv("NLP_BACKEND", "stub").lower() in ("stub", "test"):
        return _fallback_guidance(topic, language=language, accounting_standard=accounting_standard)

    base_url = os.getenv("DEEPSEEK_VLLM_URL", "http://localhost:8000/v1")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-r1-distill")
    prompt = (
        f"Provide concise accounting guidance for: {topic}. "
        f"Standard: {accounting_standard}. Language: {language}. "
        "Do not include SQL, credentials, or internal API paths."
    )
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 512,
                },
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            text = data["choices"][0]["message"]["content"]
            return sanitize_response(text)
    except Exception as exc:
        raise DeepSeekUnavailableError(str(exc)) from exc


def _fallback_guidance(*, topic: str, language: str, accounting_standard: str) -> str:
    if language == "zh-CN":
        prefix = f"（{accounting_standard} 参考信息，非法律意见）"
        guides = {
            "period_close": f"{prefix} 关账步骤：完成凭证审核、运行试算平衡、执行期末结转并关闭会计期间。",
            "reconcile": f"{prefix} 银行对账：导入银行流水、匹配内部账、处理差异并完成对账会话。",
        }
    else:
        prefix = f"({accounting_standard} informational guidance — not legal advice)"
        guides = {
            "period_close": (
                f"{prefix} To close a period: approve vouchers, run trial balance, "
                "post period-end entries, then close the accounting period."
            ),
            "reconcile": (
                f"{prefix} To reconcile: import bank transactions, match ledger entries, "
                "resolve differences, and complete the reconciliation session."
            ),
        }
    key = "period_close" if "close" in topic.lower() or "关" in topic else "reconcile"
    return sanitize_response(guides.get(key, f"{prefix} Please refer to the in-app help for '{topic}'."))
