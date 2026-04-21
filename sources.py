"""
Recupera offerte di lavoro da Himalayas API (gratuita, no auth).
Esegue query multiple con keyword diverse e deduplica per guid.
"""

import time
from datetime import datetime, timezone

import requests

BASE_URL = "https://himalayas.app/jobs/api/search"

# Keyword sets — adattale ai ruoli target del tuo profilo
QUERIES = [
    # Core — editorial leadership
    "editorial manager",
    "content lead",
    "head of content",
    "content operations manager",
    "managing editor",
    # Affiliate / partnership track (traiettoria 12-24m)
    "affiliate program manager",
    "content manager affiliate",
    "affiliate content manager",
    "content partnerships manager",
    # Performance + growth content
    "content marketing manager ecommerce",
    "ecommerce content manager",
    "growth content manager",
    "SEO content manager",
    # Figure collaterali con gap AI-bridgeable
    "newsletter manager",
    "b2b content strategist",
    "brand content manager",
]

def _is_active(job: dict) -> bool:
    """Scarta offerte scadute controllando expiryDate (Unix timestamp)."""
    expiry = job.get("expiryDate")
    if not expiry:
        return True  # se non c'è data di scadenza, assumiamo valida
    try:
        expiry_dt = datetime.fromtimestamp(int(expiry), tz=timezone.utc)
        return expiry_dt > datetime.now(tz=timezone.utc)
    except (ValueError, OSError):
        return True  # in caso di timestamp malformato, non scartare


def fetch_jobs() -> list[dict]:
    seen_guids = set()
    jobs = []

    for keyword in QUERIES:
        params = {
            "q": keyword,
            "employment_type": "Full Time",
            "sort": "recent",
        }
        try:
            resp = requests.get(BASE_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            active = 0
            for job in data.get("jobs", []):
                guid = job.get("guid")
                if guid and guid not in seen_guids and _is_active(job):
                    seen_guids.add(guid)
                    jobs.append(job)
                    active += 1

            print(f"  [{keyword}] → {active} attive su {len(data.get('jobs', []))} trovate")

        except requests.RequestException as e:
            print(f"  ERRORE per '{keyword}': {e}")

        time.sleep(0.5)

    return jobs
