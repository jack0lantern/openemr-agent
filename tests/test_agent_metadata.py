"""Unit tests for response metadata extraction (citations, confidence)."""

import json

import pytest

from app.llm.agent import _extract_response_metadata
from app.schemas import Citation, ResponseMetadata


def test_extract_response_metadata_empty_returns_none():
    """No tool calls returns None."""
    assert _extract_response_metadata(None) is None
    assert _extract_response_metadata([]) is None


def test_extract_response_metadata_non_medical_tool_returns_none():
    """Tool calls without search_medical_info return None."""
    tool_calls = [
        {"name": "get_clinic_info", "args": {}, "output": '{"clinic": {}}'},
    ]
    assert _extract_response_metadata(tool_calls) is None


def test_extract_response_metadata_medical_info_returns_citations_and_confidence():
    """search_medical_info tool call produces citations and confidence."""
    output = json.dumps({
        "conditions": [
            {"name": "Migraine", "description": "...", "common_symptoms": ["headache"], "match_score": 0.8},
            {"name": "Tension Headache", "description": "...", "common_symptoms": ["headache"], "match_score": 0.5},
        ],
        "query": "headache",
        "disclaimer": "Educational only.",
    })
    tool_calls = [
        {"name": "search_medical_info", "args": {"symptoms": "headache"}, "output": output},
    ]
    meta = _extract_response_metadata(tool_calls)
    assert meta is not None
    assert isinstance(meta, ResponseMetadata)
    assert meta.citations is not None
    assert len(meta.citations) == 2
    assert meta.citations[0].title == "Migraine"
    assert meta.citations[0].source == "OpenEMR Medical Reference"
    assert meta.citations[0].tool_name == "search_medical_info"
    assert meta.citations[0].url is None
    assert meta.confidence == 0.8
    assert meta.confidence_label == "High"


def test_extract_response_metadata_includes_url_when_present():
    """Citations include url when present in condition data."""
    output = json.dumps({
        "conditions": [
            {
                "name": "Migraine",
                "match_score": 0.8,
                "url": "https://medlineplus.gov/migraine.html",
            },
        ],
        "query": "headache",
    })
    tool_calls = [{"name": "search_medical_info", "args": {}, "output": output}]
    meta = _extract_response_metadata(tool_calls)
    assert meta is not None
    assert meta.citations is not None
    assert len(meta.citations) == 1
    assert meta.citations[0].url == "https://medlineplus.gov/migraine.html"


def test_extract_response_metadata_confidence_thresholds():
    """Confidence labels: High >= 0.7, Medium >= 0.4, Low < 0.4."""
    for score, expected_label in [(0.9, "High"), (0.7, "High"), (0.5, "Medium"), (0.4, "Medium"), (0.3, "Low")]:
        output = json.dumps({
            "conditions": [{"name": "Condition", "match_score": score}],
            "query": "x",
        })
        meta = _extract_response_metadata([
            {"name": "search_medical_info", "args": {}, "output": output},
        ])
        assert meta is not None
        assert meta.confidence == score
        assert meta.confidence_label == expected_label


def test_extract_response_metadata_empty_conditions_returns_none():
    """search_medical_info with no conditions returns None."""
    output = json.dumps({"conditions": [], "query": "xyznonexistent"})
    tool_calls = [{"name": "search_medical_info", "args": {}, "output": output}]
    assert _extract_response_metadata(tool_calls) is None


def test_extract_response_metadata_invalid_json_skips_tool():
    """Invalid JSON in tool output is skipped."""
    tool_calls = [
        {"name": "search_medical_info", "args": {}, "output": "not valid json"},
    ]
    assert _extract_response_metadata(tool_calls) is None

def test_extract_response_metadata_pharmaceutical_info_returns_citations():
    """search_pharmaceutical_info tool call produces citations and confidence."""
    output = json.dumps({
        "medications": [
            {"name": "Lisinopril", "description": "...", "common_uses": ["high blood pressure"], "match_score": 0.9},
        ],
        "query": "blood pressure",
        "disclaimer": "Educational only.",
    })
    tool_calls = [
        {"name": "search_pharmaceutical_info", "args": {"query": "blood pressure"}, "output": output},
    ]
    meta = _extract_response_metadata(tool_calls)
    assert meta is not None
    assert isinstance(meta, ResponseMetadata)
    assert meta.citations is not None
    assert len(meta.citations) == 1
    assert meta.citations[0].title == "Lisinopril"
    assert meta.citations[0].source == "OpenEMR Medical Reference"
    assert meta.citations[0].tool_name == "search_pharmaceutical_info"
    assert meta.confidence == 0.9
    assert meta.confidence_label == "High"
