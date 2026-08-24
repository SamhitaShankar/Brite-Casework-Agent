"""
Client for the Calder County Resident History API.
Connects to http://127.0.0.1:8083 or falls back seamlessly to the immutable data file.
"""
import os
import json
import logging
import asyncio
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

logger = logging.getLogger("brite.history_client")

HISTORY_API_BASE_URL = os.getenv("HISTORY_API_URL", "http://127.0.0.1:8083")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FALLBACK_PATH = os.path.join(HERE, "..", "services", "_history_data.json")


class HistoryServiceClient:
    def __init__(self, base_url: str = HISTORY_API_BASE_URL):
        self.base_url = base_url.rstrip("/")

    def _sync_get_resident(self, resident_ref: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/residents/{resident_ref}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=3.0) as response:
                if response.status == 200:
                    return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception as e:
            logger.debug(f"History API connect {url} fallback: {e}")

        # Fallback reading from immutable dataset
        return self._read_local_data(resident_ref)

    async def get_resident(self, resident_ref: str) -> Optional[Dict[str, Any]]:
        """Fetch full history record for a resident."""
        return await asyncio.to_thread(self._sync_get_resident, resident_ref)

    async def get_household(self, resident_ref: str) -> Optional[Dict[str, Any]]:
        """Fetch household composition only."""
        rec = await self.get_resident(resident_ref)
        if rec and "household" in rec:
            return {"resident_ref": resident_ref, "household": rec["household"]}
        return None

    async def get_events(self, resident_ref: str) -> Optional[Dict[str, Any]]:
        """Fetch case events only."""
        rec = await self.get_resident(resident_ref)
        if rec and "events" in rec:
            return {"resident_ref": resident_ref, "events": rec["events"]}
        return None

    _HISTORY_CACHE = None

    def _read_local_data(self, resident_ref: str) -> Optional[Dict[str, Any]]:
        if self.__class__._HISTORY_CACHE is None:
            if os.path.exists(DATA_FALLBACK_PATH):
                with open(DATA_FALLBACK_PATH, "r", encoding="utf-8") as f:
                    self.__class__._HISTORY_CACHE = json.load(f)
            else:
                self.__class__._HISTORY_CACHE = {}
                
        return self.__class__._HISTORY_CACHE.get(resident_ref)
