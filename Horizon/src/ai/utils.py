"""Shared AI utility functions."""

import json
import re
from typing import Optional


def strip_surrogates(text: str) -> str:
    """Remove unpaired surrogate code points (broken emoji) from text.

    Surrogates (U+D800–U+DFFF) are invalid in UTF-8 and crash file writes or
    API requests. They leak in from mangled emoji in web-search results or AI
    JSON responses (e.g. a lone ``\\ud83d`` escape). Removing them is safe —
    they never encode real text.
    """
    if not isinstance(text, str) or not any(
        0xD800 <= ord(ch) <= 0xDFFF for ch in text
    ):
        return text
    return "".join(ch for ch in text if not 0xD800 <= ord(ch) <= 0xDFFF)


def clean_surrogates(value):
    """Recursively strip surrogate characters from JSON-parsed values."""
    if isinstance(value, str):
        return strip_surrogates(value)
    if isinstance(value, dict):
        return {k: clean_surrogates(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_surrogates(v) for v in value]
    return value


def parse_json_response(response: str) -> Optional[dict]:
    """Try multiple strategies to extract a JSON object from an AI response.

    Returns the parsed dict, or None if all strategies fail.
    """
    text = response.strip()

    def _loads(raw: str) -> dict:
        return clean_surrogates(json.loads(raw))

    # Strategy 1: direct parse
    try:
        return _loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Strategy 2: extract from ```json ... ``` code block
    if "```json" in text:
        try:
            json_str = text.split("```json")[1].split("```")[0].strip()
            return _loads(json_str)
        except (json.JSONDecodeError, ValueError, IndexError):
            pass

    # Strategy 3: extract from ``` ... ``` code block
    if "```" in text:
        try:
            json_str = text.split("```")[1].split("```")[0].strip()
            return _loads(json_str)
        except (json.JSONDecodeError, ValueError, IndexError):
            pass

    # Strategy 4: find the first { ... } block using brace matching
    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return _loads(text[start : i + 1])
                    except (json.JSONDecodeError, ValueError):
                        break

    # Strategy 5: regex extraction as last resort
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return _loads(match.group())
        except (json.JSONDecodeError, ValueError):
            pass

    return None
