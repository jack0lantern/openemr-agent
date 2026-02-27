"""
Unit tests for _tool_calls_to_json.

Prevents regression of AttributeError: 'dict' object has no attribute 'model_dump'
when the agent returns plain dicts from debug_tool_calls instead of ToolCallDebug models.
"""

import pytest

from app.api.patient import _tool_calls_to_json
from app.schemas import ToolCallDebug


def test_tool_calls_to_json_none_returns_none():
    """None input returns None."""
    assert _tool_calls_to_json(None) is None


def test_tool_calls_to_json_empty_list_returns_none():
    """Empty list returns None."""
    assert _tool_calls_to_json([]) is None


def test_tool_calls_to_json_dict_input_returns_dicts():
    """Plain dicts (from agent debug_tool_calls) are returned as-is without model_dump."""
    tool_calls = [
        {"name": "get_clinic_info", "args": {}, "output": "Clinic is open 9-5."},
        {"name": "get_current_datetime", "args": {}, "output": "2025-02-24T12:00:00Z"},
    ]
    result = _tool_calls_to_json(tool_calls)
    assert result == tool_calls


def test_tool_calls_to_json_toolcalldebug_input_returns_dicts():
    """ToolCallDebug models are serialized via model_dump()."""
    tool_calls = [
        ToolCallDebug(name="get_clinic_info", args={}, output="Clinic is open 9-5."),
        ToolCallDebug(name="get_current_datetime", args={"tz": "UTC"}, output="2025-02-24"),
    ]
    result = _tool_calls_to_json(tool_calls)
    assert result == [
        {"name": "get_clinic_info", "args": {}, "output": "Clinic is open 9-5."},
        {"name": "get_current_datetime", "args": {"tz": "UTC"}, "output": "2025-02-24"},
    ]


def test_tool_calls_to_json_mixed_input_handles_both():
    """Mixed dict and ToolCallDebug items are both serialized correctly."""
    tool_calls = [
        {"name": "get_clinic_info", "args": {}, "output": "Clinic info"},
        ToolCallDebug(name="get_current_datetime", args={}, output="2025-02-24"),
    ]
    result = _tool_calls_to_json(tool_calls)
    assert result == [
        {"name": "get_clinic_info", "args": {}, "output": "Clinic info"},
        {"name": "get_current_datetime", "args": {}, "output": "2025-02-24"},
    ]
