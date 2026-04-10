"""
AI client abstraction over Anthropic's API.

Swap the provider by replacing AnthropicClient with another implementation
of the same interface — the rest of the codebase is unaffected.
"""
import asyncio
import json
import re
import time
from dataclasses import dataclass
from functools import lru_cache

import anthropic
import structlog

from app.config import get_settings
from app.core.exceptions import ServiceUnavailableError

logger = structlog.get_logger()

_SYSTEM_PROMPT = """\
You are an expert software debugger specializing in API errors and stack traces.
Analyze the provided error, identify its root cause, and suggest concrete fixes.
Respond with ONLY valid JSON — no markdown, no explanation outside the JSON object.\
"""


@dataclass
class AnalysisResult:
    summary: str
    root_cause: str
    suggestions: list[dict[str, str]]
    model: str
    tokens_used: int
    duration_ms: int


class AnthropicClient:
    def __init__(self, api_key: str, model: str, timeout: float) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._timeout = timeout

    async def analyze_error(
        self,
        title: str,
        raw_error: str,
        context: dict | None,
    ) -> AnalysisResult:
        prompt = _build_prompt(title, raw_error, context)
        start = time.perf_counter()

        message = await asyncio.wait_for(
            self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            ),
            timeout=self._timeout,
        )

        duration_ms = int((time.perf_counter() - start) * 1000)
        tokens_used = message.usage.input_tokens + message.usage.output_tokens
        raw_text = message.content[0].text

        parsed = _parse_json_response(raw_text)

        logger.info(
            "ai_analysis_complete",
            model=self._model,
            tokens=tokens_used,
            duration_ms=duration_ms,
        )

        return AnalysisResult(
            summary=parsed["summary"],
            root_cause=parsed["root_cause"],
            suggestions=parsed.get("suggestions", []),
            model=self._model,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
        )


# ---------------------------------------------------------------------------
# Singleton — lru_cache is atomic; no mutable global needed
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _make_client() -> AnthropicClient:
    """Built once per process. lru_cache does not cache raised exceptions."""
    settings = get_settings()
    if not settings.ANTHROPIC_API_KEY:
        raise ServiceUnavailableError(
            "AI analysis is not configured — set ANTHROPIC_API_KEY"
        )
    return AnthropicClient(
        api_key=settings.ANTHROPIC_API_KEY,
        model=settings.AI_MODEL,
        timeout=settings.AI_TIMEOUT_SECONDS,
    )


def get_ai_client() -> AnthropicClient:
    return _make_client()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_prompt(title: str, raw_error: str, context: dict | None) -> str:
    """XML delimiters isolate user content from instructions.
    Not a complete injection defence, but significantly raises the bar."""
    context_block = ""
    if context:
        context_block = f"\n<context>\n{json.dumps(context, indent=2)}\n</context>\n"

    return f"""\
Analyze the following API error.

<error_title>{title}</error_title>
{context_block}
<error_log>
{raw_error}
</error_log>

Respond with ONLY a JSON object using this exact shape:
{{
  "summary": "One to two sentence plain-language summary of what failed",
  "root_cause": "Technical explanation of why it failed",
  "suggestions": [
    {{"step": 1, "action": "First concrete step to investigate or fix"}},
    {{"step": 2, "action": "Second step"}}
  ]
}}\
"""


def _parse_json_response(text: str) -> dict:
    """Parses AI output as JSON. Handles accidental markdown fences."""
    stripped = text.strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", stripped)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Log the content internally but do NOT include it in the exception —
    # the AI may echo back fragments of user-submitted error content.
    logger.warning("ai_non_json_response", preview=stripped[:120])
    raise ValueError("AI returned a response that could not be parsed as JSON")
