"""Tests for symptom to ICD-10 mapping."""

import pytest

from app.data.symptom_icd_mapping import get_icd_codes_for_symptoms


def test_get_icd_codes_headache_nausea():
    """Headache and nausea map to Migraine and Gastroenteritis codes."""
    codes = get_icd_codes_for_symptoms("headache nausea")
    assert "G43.1" in codes  # Migraine
    assert "A09" in codes  # Gastroenteritis


def test_get_icd_codes_migraine():
    """Migraine maps to G43.1."""
    codes = get_icd_codes_for_symptoms("migraine")
    assert "G43.1" in codes


def test_get_icd_codes_empty():
    """Empty query returns empty list."""
    assert get_icd_codes_for_symptoms("") == []
    assert get_icd_codes_for_symptoms(None) == []
