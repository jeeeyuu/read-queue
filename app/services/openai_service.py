"""OpenAI Responses API integration for Korean title/summary generation."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from app.utils.http_utils import request_with_retry
from app.utils.text_utils import truncate_text


class OpenAIService:
    """Generates cleaned Korean titles and concise one-line summaries."""

    def __init__(
        self,
        api_key: str,
        model: str,
        language: str = "ko",
        timeout_seconds: int = 20,
        max_input_chars: int = 4000,
        prompt_path: str = "app/prompts/summarize_link.txt",
        max_retries: int = 3,
        retry_backoff_seconds: int = 2,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._language = language
        self._timeout = timeout_seconds
        self._max_input_chars = max_input_chars
        self._prompt = Path(prompt_path).read_text(encoding="utf-8")
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds

    def summarize(
        self,
        url: str,
        original_title: str | None,
        excerpt: str | None,
    ) -> tuple[str | None, str | None, str | None]:
        """Return (cleaned_title_ko, summary_one_line_ko, error)."""

        clipped_title = truncate_text(original_title or "", self._max_input_chars)
        clipped_excerpt = truncate_text(excerpt or "", self._max_input_chars)

        if not clipped_title and not clipped_excerpt:
            return None, None, "insufficient source text"

        prompt = self._prompt.format(
            language=self._language,
            url=url,
            original_title=clipped_title or "(없음)",
            excerpt=clipped_excerpt or "(없음)",
        )

        payload = {
            "model": self._model,
            "input": prompt,
            "text": {"format": {"type": "json_object"}},
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            def _call() -> dict:
                with httpx.Client(timeout=self._timeout) as client:
                    resp = client.post("https://api.openai.com/v1/responses", headers=headers, json=payload)
                    resp.raise_for_status()
                    return resp.json()

            body = request_with_retry(_call, self._max_retries, self._retry_backoff_seconds)
        except Exception as exc:  # noqa: BLE001
            return None, None, f"openai call failed: {exc}"

        text_out = body.get("output_text")
        if not text_out and body.get("output"):
            # Fallback parser for structured response blocks.
            chunks = []
            for item in body.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        chunks.append(content.get("text", ""))
            text_out = "\n".join(chunks).strip()

        if not text_out:
            return None, None, "openai response missing output_text"

        try:
            parsed = json.loads(text_out)
        except json.JSONDecodeError:
            return None, None, "openai response not valid JSON"

        cleaned_title = parsed.get("cleaned_title_ko")
        summary = parsed.get("summary_one_line_ko")

        if not cleaned_title and not summary:
            return None, None, "openai response missing fields"
        return cleaned_title, summary, None
