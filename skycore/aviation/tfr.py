"""FAA Temporary Flight Restrictions (TFR) fetcher.

FAA publishes TFRs as a JSON feed (no API key needed). For drone pilots,
active TFRs near you mean STOP — they're issued for VIP movements,
wildfires, sporting events, and other operational restrictions.

Returns raw entries; downstream code can filter by location.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

FAA_TFR_FEED = "https://tfr.faa.gov/tfr_map_ws/getTFRs.do"


@dataclass
class Tfr:
    notam_id: str
    type: str
    description: str
    effective_from: Optional[str]
    effective_to: Optional[str]
    raw: dict


def fetch_tfrs(timeout_s: float = 15.0) -> list[Tfr]:
    """Fetch the current US TFR list. Best-effort — the FAA service is rate-limited and occasionally returns HTML."""
    out: list[Tfr] = []
    try:
        req = urllib.request.Request(FAA_TFR_FEED, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            text = resp.read().decode("utf-8")
        if not text.strip().startswith(("[", "{")):
            log.info("FAA TFR endpoint returned non-JSON; manual check at https://tfr.faa.gov")
            return out
        data = json.loads(text)
        items = data if isinstance(data, list) else data.get("tfrs") or []
        for it in items:
            out.append(Tfr(
                notam_id=it.get("notamID", ""),
                type=it.get("type", ""),
                description=it.get("description", ""),
                effective_from=it.get("effDate"),
                effective_to=it.get("expDate"),
                raw=it,
            ))
    except Exception as e:
        log.warning("TFR fetch failed: %s", e)
    return out
