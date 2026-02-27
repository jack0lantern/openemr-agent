"""Shared utility for tool modules."""

import json


def _tool_result(data: dict) -> str:
    """Serialize structured data as JSON for the LLM to parse."""
    return json.dumps(data, indent=2)
