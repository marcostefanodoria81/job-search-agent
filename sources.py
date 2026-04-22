"""
Recupera offerte di lavoro da più fonti gratuite e le normalizza
in un formato comune compatibile con lo scorer.

Fonti attive:
  - Himalayas  (JSON API, no auth)
  - Remotive   (JSON API, no auth)
  - Remote OK  (JSON API, no auth)
  - We Work Remotely (RSS, no auth)
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# Himalayas
# ---------------------------------------------------------------------------

HIMALAYAS_BASE = "https://himalayas.app/jobs/api/search"

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
        return True
    try:
        expiry_dt = datetime.fromtimestamp(int(expiry), tz=timezone.utc)
        return expiry_dt > datetime.now(tz=timezone.utc)
    except (ValueError, OSError):
        return True


def _fetch_himalayas(seen_guids: set) -> list[dict]:
    jobs = []
    for keyword in QUERIES:
        params = {"q": keyword, "employment_type": "Full Time", "sort": "recent"}
        try:
            resp = requests.get(HIMALAYAS_BASE, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            active = 0
            for job in data.get("jobs", []):
                guid = job.get("guid")
                if guid and guid not in seen_guids and _is_active(job):
                    seen_guids.add(guid)
                    job["_source"] = "himalayas"
                    jobs.append(job)
                    active += 1
            print(f"    [{keyword}] → {active} nuove")
        except requests.RequestException as e:
            print(f"    ERRORE Himalayas '{keyword}': {e}")
        time.sleep(0.5)
    return jobs


# ---------------------------------------------------------------------------
# Remotive
# ---------------------------------------------------------------------------

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
REMOTIVE_CATEGORIES = ["marketing", "copywriting"]


def _normalize_remotive(job: dict) -> dict:
    location = job.get("candidate_required_location") or ""
    return {
        "title": job.get("title") or "",
        "companyName": job.get("company_name") or "",
        "description": job.get("description") or "",
        "excerpt": "",
        "minSalary": None,
        "maxSalary": None,
        "currency": "USD",
        "locationRestrictions": [location] if location else [],
        "applicationLink": job.get("url", ""),
        "pubDate": job.get("publication_date", ""),
        "guid": f"remotive-{job.get('id', '')}",
        "expiryDate": None,
        "_source": "remotive",
    }


def _fetch_remotive(seen_guids: set) -> list[dict]:
    jobs = []
    for category in REMOTIVE_CATEGORIES:
        try:
            resp = requests.get(
                REMOTIVE_URL, params={"category": category, "limit": 100}, timeout=15
            )
            resp.raise_for_status()
            active = 0
            for job in resp.json().get("jobs", []):
                guid = f"remotive-{job.get('id', '')}"
                if guid not in seen_guids:
                    seen_guids.add(guid)
                    jobs.append(_normalize_remotive(job))
                    active += 1
            print(f"    [Remotive/{category}] → {active} nuove")
        except requests.RequestException as e:
            print(f"    ERRORE Remotive '{category}': {e}")
        time.sleep(0.5)
    return jobs


# ---------------------------------------------------------------------------
# Remote OK
# ---------------------------------------------------------------------------

REMOTE_OK_URL = "https://remoteok.com/api"
REMOTE_OK_TAGS = ["content", "marketing", "editorial"]


def _normalize_remote_ok(job: dict) -> dict:
    return {
        "title": job.get("position") or "",
        "companyName": job.get("company") or "",
        "description": job.get("description") or "",
        "excerpt": "",
        "minSalary": job.get("salary_min"),
        "maxSalary": job.get("salary_max"),
        "currency": "USD",
        "locationRestrictions": [],
        "applicationLink": job.get("apply_url") or job.get("url", ""),
        "pubDate": job.get("date", ""),
        "guid": f"remoteok-{job.get('id', job.get('slug', ''))}",
        "expiryDate": None,
        "_source": "remoteok",
    }


def _fetch_remote_ok(seen_guids: set) -> list[dict]:
    jobs = []
    for tag in REMOTE_OK_TAGS:
        try:
            resp = requests.get(
                REMOTE_OK_URL,
                params={"tags": tag},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            resp.raise_for_status()
            # Il primo elemento dell'array è metadata, lo saltiamo
            items = [j for j in resp.json() if isinstance(j, dict) and "position" in j]
            active = 0
            for job in items:
                guid = f"remoteok-{job.get('id', job.get('slug', ''))}"
                if guid not in seen_guids:
                    seen_guids.add(guid)
                    jobs.append(_normalize_remote_ok(job))
                    active += 1
            print(f"    [RemoteOK/{tag}] → {active} nuove")
        except requests.RequestException as e:
            print(f"    ERRORE RemoteOK '{tag}': {e}")
        time.sleep(1)  # RemoteOK è più sensibile al rate limiting
    return jobs


# ---------------------------------------------------------------------------
# We Work Remotely
# ---------------------------------------------------------------------------

WWR_RSS_URLS = [
    "https://weworkremotely.com/categories/remote-marketing-jobs.rss",
]


def _normalize_wwr(item: ET.Element) -> dict | None:
    title_el = item.find("title")
    link_el = item.find("link")
    desc_el = item.find("description")
    pub_el = item.find("pubDate")
    guid_el = item.find("guid")

    if title_el is None or not title_el.text:
        return None

    raw_title = title_el.text.strip()
    # Formato WWR: "Company Name: Job Title"
    if ": " in raw_title:
        company, title = raw_title.split(": ", 1)
    else:
        company, title = "N/D", raw_title

    link = link_el.text.strip() if link_el is not None and link_el.text else ""
    guid_text = guid_el.text.strip() if guid_el is not None and guid_el.text else link

    return {
        "title": title.strip(),
        "companyName": company.strip(),
        "description": desc_el.text or "" if desc_el is not None else "",
        "excerpt": "",
        "minSalary": None,
        "maxSalary": None,
        "currency": "USD",
        "locationRestrictions": [],
        "applicationLink": link,
        "pubDate": pub_el.text or "" if pub_el is not None else "",
        "guid": f"wwr-{guid_text}",
        "expiryDate": None,
        "_source": "weworkremotely",
    }


def _fetch_wwr(seen_guids: set) -> list[dict]:
    jobs = []
    for url in WWR_RSS_URLS:
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            active = 0
            for item in root.findall(".//item"):
                job = _normalize_wwr(item)
                if job and job["guid"] not in seen_guids:
                    seen_guids.add(job["guid"])
                    jobs.append(job)
                    active += 1
            print(f"    [WeWorkRemotely] → {active} nuove")
        except (requests.RequestException, ET.ParseError) as e:
            print(f"    ERRORE WWR: {e}")
        time.sleep(0.5)
    return jobs


# ---------------------------------------------------------------------------
# LinkedIn via Apify
# ---------------------------------------------------------------------------

APIFY_ACTOR = "curious_coder~linkedin-jobs-scraper"
APIFY_BASE = "https://api.apify.com/v2"

# Subset di query — LinkedIn è più lento e costa crediti, usiamo le keyword più mirate
LINKEDIN_QUERIES = [
    "editorial manager",
    "head of content",
    "content operations manager",
    "affiliate program manager",
    "content marketing manager",
    "newsletter manager",
]


def _normalize_linkedin(job: dict) -> dict:
    return {
        "title": job.get("title") or "",
        "companyName": job.get("companyName") or job.get("company") or "",
        "description": job.get("descriptionText") or job.get("description") or "",
        "excerpt": "",
        "minSalary": None,
        "maxSalary": None,
        "currency": "USD",
        "locationRestrictions": [job["location"]] if job.get("location") else [],
        "applicationLink": job.get("applyUrl", "") or job.get("jobUrl", ""),
        "pubDate": job.get("postedAt", "") or job.get("publishedAt", ""),
        "guid": f"linkedin-{job.get('id', job.get('trackingId', ''))}",
        "expiryDate": None,
        "_source": "linkedin",
    }


def _fetch_linkedin(seen_guids: set) -> list[dict]:
    import os
    api_key = os.environ.get("APIFY_API_KEY")

    if not api_key:
        print("    [LinkedIn] APIFY_API_KEY non trovata — salto.")
        return []

    jobs = []
    for keyword in LINKEDIN_QUERIES:
        try:
            resp = requests.post(
                f"{APIFY_BASE}/acts/{APIFY_ACTOR}/run-sync-get-dataset-items",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "searchKeywords": keyword,
                    "location": "Worldwide",
                    "count": 25,
                    "contractType": "fulltime",
                },
                timeout=120,
            )
            resp.raise_for_status()
            active = 0
            for job in resp.json():
                guid = f"linkedin-{job.get('id', job.get('trackingId', ''))}"
                if guid and guid not in seen_guids:
                    seen_guids.add(guid)
                    jobs.append(_normalize_linkedin(job))
                    active += 1
            print(f"    [LinkedIn/{keyword}] → {active} nuove")
        except requests.RequestException as e:
            print(f"    ERRORE LinkedIn '{keyword}': {e}")
        time.sleep(2)

    return jobs


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def fetch_jobs(with_linkedin: bool = False) -> list[dict]:
    seen_guids: set = set()
    jobs = []

    print("  → Himalayas")
    jobs += _fetch_himalayas(seen_guids)

    print("  → Remotive")
    jobs += _fetch_remotive(seen_guids)

    print("  → Remote OK")
    jobs += _fetch_remote_ok(seen_guids)

    print("  → We Work Remotely")
    jobs += _fetch_wwr(seen_guids)

    if with_linkedin:
        print("  → LinkedIn (Apify)")
        jobs += _fetch_linkedin(seen_guids)
    else:
        print("  → LinkedIn (Apify) — saltato (usa --with-linkedin per includerlo)")

    return jobs
