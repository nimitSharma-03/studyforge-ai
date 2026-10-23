"""Optional adapter for a locally running Ollama server.

Disabled unless OLLAMA_URL is set. The baseline application never depends on it, no model
is downloaded automatically, and failures are reported instead of being masked with
fabricated output. Point OLLAMA_URL only at a server you control: the retrieved passages
from the user's document are sent to it.
"""

from __future__ import annotations

import httpx

from app.config import get_settings


class LLMUnavailable(Exception):
    pass


PROMPT = """You are a study assistant. Using ONLY the source passages below, write a clear explanation of the topic
"{topic}" for a college student preparing for an exam. Use short paragraphs and bullet points. If the passages do not
contain enough information, say so instead of adding outside knowledge. Cite passages as [1], [2], ...

{passages}

Explanation:"""


def explain_topic(topic: str, passages: list[str]) -> tuple[str, str]:
    settings = get_settings()
    if not settings.llm_enabled:
        raise LLMUnavailable("No local language model is configured (OLLAMA_URL is not set).")
    numbered = "\n\n".join(f"[{i + 1}] {p}" for i, p in enumerate(passages))
    payload = {
        "model": settings.ollama_model,
        "prompt": PROMPT.format(topic=topic, passages=numbered),
        "stream": False,
        "options": {"temperature": 0.2},
    }
    try:
        response = httpx.post(
            settings.ollama_url.rstrip("/") + "/api/generate", json=payload, timeout=settings.ollama_timeout_seconds
        )
        response.raise_for_status()
        text = (response.json().get("response") or "").strip()
    except httpx.TimeoutException as exc:
        raise LLMUnavailable("The local language model did not respond in time.") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise LLMUnavailable("The local language model could not be reached or returned an invalid response.") from exc
    if not text:
        raise LLMUnavailable("The local language model returned an empty response.")
    return text, settings.ollama_model
