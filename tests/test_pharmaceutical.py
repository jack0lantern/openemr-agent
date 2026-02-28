import os

import pytest

from app.llm.tools.medical_info_tools import search_pharmaceutical_info


@pytest.fixture(autouse=True)
def use_mock_data():
    """Ensure mock data is used for pharmaceutical tests."""
    prev = os.environ.get("USE_MOCK_DATA")
    os.environ["USE_MOCK_DATA"] = "true"
    yield
    if prev is not None:
        os.environ["USE_MOCK_DATA"] = prev
    else:
        os.environ.pop("USE_MOCK_DATA", None)


def test_search_pharmaceutical_info():
    result = search_pharmaceutical_info.invoke({"query": "lisinopril"})
    assert "Lisinopril" in result
    assert "blood pressure" in result


def test_search_pharmaceutical_info_warfarin_interactions_includes_url():
    """Warfarin interaction query returns medication with source URL for citations."""
    result = search_pharmaceutical_info.invoke({"query": "warfarin what meds interact with it"})
    assert "Warfarin" in result
    assert "medlineplus.gov" in result or "a682277" in result
    assert "aspirin" in result or "interact" in result.lower()


def test_search_pharmaceutical_info_empty():
    result = search_pharmaceutical_info.invoke({"query": ""})
    assert "Please provide a medication name" in result

