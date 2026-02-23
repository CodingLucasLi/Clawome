"""Shared utility for extracting JSON from LLM responses."""

import json
import re


def extract_json(text: str) -> dict:
    """Extract JSON from an LLM response, handling markdown code fences."""
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    return json.loads(text)
