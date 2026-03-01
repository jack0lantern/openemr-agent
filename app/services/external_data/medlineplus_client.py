"""MedlinePlus Connect client for drug and condition information with source URLs."""

import logging
import os
import re
import httpx

logger = logging.getLogger(__name__)

_MEDLINE_BASE = os.getenv("MEDLINE_CONNECT_URL", "https://connect.medlineplus.gov/service")
_RXNORM_OID = "2.16.840.1.113883.6.88"
_ICD10CM_OID = "2.16.840.1.113883.6.90"
_TIMEOUT = 10.0


def _parse_entry(entry: dict) -> dict | None:
    """Extract title, url, summary from MedlinePlus Connect entry."""
    title_obj = entry.get("title", {})
    title = title_obj.get("_value", "") if isinstance(title_obj, dict) else str(title_obj)
    if not title:
        return None
    links = entry.get("link", [])
    if isinstance(links, dict):
        links = [links]
    url = ""
    for link in links or []:
        href = link.get("href", "") if isinstance(link, dict) else ""
        if href and "medlineplus.gov" in href:
            url = href
            break
    summary_obj = entry.get("summary", {})
    summary = summary_obj.get("_value", "") if isinstance(summary_obj, dict) else str(summary_obj)
    if summary:
        summary = re.sub(r"<[^>]+>", " ", summary)
        summary = " ".join(summary.split()).strip()
    return {"title": title, "url": url or None, "summary": summary}


def get_drug_info(rxcui: str) -> list[dict]:
    """
    Fetch drug information from MedlinePlus Connect by RXCUI.
    Returns list of {title, url, summary} dicts.
    """
    if not rxcui or not str(rxcui).strip():
        return []
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(
                _MEDLINE_BASE,
                params={
                    "mainSearchCriteria.v.cs": _RXNORM_OID,
                    "mainSearchCriteria.v.c": str(rxcui).strip(),
                    "knowledgeResponseType": "application/json",
                },
            )
        if resp.status_code != 200:
            logger.warning("MedlinePlus drug request failed: status=%s", resp.status_code)
            return []
        data = resp.json()
        feed = data.get("feed", {})
        entries = feed.get("entry", [])
        if isinstance(entries, dict):
            entries = [entries]
        result = []
        for e in entries or []:
            parsed = _parse_entry(e)
            if parsed and parsed.get("title"):
                result.append(parsed)
        return result
    except Exception as e:
        logger.exception("MedlinePlus get_drug_info failed: %s", e)
        return []


def get_condition_info(icd10: str) -> list[dict]:
    """
    Fetch condition information from MedlinePlus Connect by ICD-10-CM code.
    Returns list of {title, url, summary} dicts.
    """
    if not icd10 or not str(icd10).strip():
        return []
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(
                _MEDLINE_BASE,
                params={
                    "mainSearchCriteria.v.cs": _ICD10CM_OID,
                    "mainSearchCriteria.v.c": str(icd10).strip().upper(),
                    "knowledgeResponseType": "application/json",
                },
            )
        if resp.status_code != 200:
            logger.warning("MedlinePlus condition request failed: status=%s", resp.status_code)
            return []
        data = resp.json()
        feed = data.get("feed", {})
        entries = feed.get("entry", [])
        if isinstance(entries, dict):
            entries = [entries]
        result = []
        for e in entries or []:
            parsed = _parse_entry(e)
            if parsed and parsed.get("title"):
                result.append(parsed)
        return result
    except Exception as e:
        logger.exception("MedlinePlus get_condition_info failed: %s", e)
        return []
