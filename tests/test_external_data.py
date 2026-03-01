"""Tests for external data clients (RxNav, MedlinePlus Connect)."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.external_data.medlineplus_client import get_condition_info, get_drug_info
from app.services.external_data.rxnav_client import find_rxcui


def test_find_rxcui_mocked():
    """RxNav returns RXCUI from drug name."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"idGroup": {"rxnormId": ["11289"]}}
    with patch("httpx.Client") as MockClient:
        MockClient.return_value.__enter__.return_value.get.return_value = mock_resp
        rxcui = find_rxcui("warfarin")
    assert rxcui == "11289"


def test_find_rxcui_empty():
    """RxNav returns None for empty input."""
    assert find_rxcui("") is None
    assert find_rxcui(None) is None


def test_get_drug_info_mocked():
    """MedlinePlus returns drug info with URL."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "feed": {
            "entry": [
                {
                    "title": {"_value": "Warfarin"},
                    "link": [{"href": "https://medlineplus.gov/druginfo/meds/a682277.html"}],
                    "summary": {"_value": "Warfarin is an anticoagulant."},
                }
            ]
        }
    }
    with patch("httpx.Client") as MockClient:
        MockClient.return_value.__enter__.return_value.get.return_value = mock_resp
        result = get_drug_info("11289")
    assert len(result) == 1
    assert result[0]["title"] == "Warfarin"
    assert "medlineplus.gov" in (result[0]["url"] or "")
    assert "anticoagulant" in result[0]["summary"]


def test_get_condition_info_mocked():
    """MedlinePlus returns condition info with URL."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "feed": {
            "entry": [
                {
                    "title": {"_value": "Migraine"},
                    "link": [{"href": "https://medlineplus.gov/migraine.html"}],
                    "summary": {"_value": "Migraines are recurring headaches."},
                }
            ]
        }
    }
    with patch("httpx.Client") as MockClient:
        MockClient.return_value.__enter__.return_value.get.return_value = mock_resp
        result = get_condition_info("G43.1")
    assert len(result) == 1
    assert result[0]["title"] == "Migraine"
    assert "medlineplus.gov" in (result[0]["url"] or "")
    assert "headache" in result[0]["summary"].lower()
