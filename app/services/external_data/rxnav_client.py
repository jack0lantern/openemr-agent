"""RxNav REST client for drug name to RXCUI resolution."""

import logging
import os
import httpx

logger = logging.getLogger(__name__)

_RXNAV_BASE = os.getenv("RXNAV_BASE_URL", "https://rxnav.nlm.nih.gov/REST")
_TIMEOUT = 10.0


def find_rxcui(drug_name: str) -> str | None:
    """
    Resolve drug name to RxNorm concept ID (RXCUI).
    Returns first RXCUI or None if not found.
    """
    name = (drug_name or "").strip()
    if not name:
        return None
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(
                f"{_RXNAV_BASE}/rxcui.json",
                params={"name": name},
            )
        if resp.status_code != 200:
            logger.warning("RxNav rxcui request failed: status=%s", resp.status_code)
            return None
        data = resp.json()
        ids = data.get("idGroup", {}).get("rxnormId")
        if ids and isinstance(ids, list) and len(ids) > 0:
            return str(ids[0])
        return None
    except Exception as e:
        logger.exception("RxNav find_rxcui failed: %s", e)
        return None
