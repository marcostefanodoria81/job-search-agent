"""
Scorer rule-based — nessuna chiamata API, nessun costo.
Valuta ogni offerta controllando keyword nel titolo e nella descrizione
contro le dimensioni della rubrica di scoring.

Meno preciso di Claude Haiku ma funziona a costo zero come primo filtro.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Keyword lists per dimensione
# ---------------------------------------------------------------------------

# Criteri eliminatori
GAMING_KEYWORDS = ["gaming", "game studio", "esports", "e-sports", "video game"]
CRYPTO_KEYWORDS = ["crypto", "blockchain", "web3", "nft", "defi", "bitcoin", "ethereum", "dao"]
ENTRY_LEVEL_KEYWORDS = ["junior", "entry level", "entry-level", "internship", "intern ", "trainee", "apprendista"]
NOT_REMOTE_KEYWORDS = ["on-site only", "in-office", "no remote", "onsite required"]

# Location incompatibili con Marco
# Se locationRestrictions contiene SOLO queste aree, il ruolo è eliminatorio
GEO_INCOMPATIBLE = [
    "united states", "us only", "usa only", "canada only",
    "latin america", "latam", "brazil", "argentina", "colombia", "mexico",
    "philippines", "india", "pakistan", "nigeria", "indonesia",
    "south korea", "singapore", "australia", "new zealand",
    "united kingdom",  # UK-only = incompatibile (no EU post-Brexit)
]
# Qualsiasi presenza di questi segnala compatibilità con Marco → non eliminare
GEO_COMPATIBLE = [
    # Segnali espliciti worldwide
    "worldwide", "anywhere", "global", "international", "remote",
    # Regioni che includono l'Italia
    "europe", "eu", "emea", "cet", "cest", "utc+1", "utc+2",
    # Paesi EU — Marco ha libertà di movimento e permesso di lavoro
    "italy", "germany", "france", "spain", "netherlands", "portugal",
    "austria", "belgium", "sweden", "denmark", "finland", "ireland",
    "poland", "czechia", "hungary", "romania", "greece", "croatia",
    "slovakia", "slovenia", "bulgaria", "luxembourg", "malta", "cyprus",
    "estonia", "latvia", "lithuania",
    # Paesi extra-EU con mercato del lavoro remote-friendly verso EU
    "switzerland", "norway", "iceland",
]

# Dimensione 1 — Fit ruolo (30 punti)
ROLE_TIER1 = [  # 30 pt — editorial leadership con team
    "editorial manager", "head of editorial", "editorial director",
    "content lead", "head of content", "director of content",
    "content operations manager", "managing editor",
]
ROLE_TIER2 = [  # 22 pt — content manager con ownership strategica
    "content manager", "content marketing manager", "editorial and content",
    "content strategist", "content strategy manager",
    "brand content manager", "content partnerships manager",
    "newsletter manager", "email content manager",
]
ROLE_TIER3 = [  # 18 pt — content marketing + SEO/performance
    "seo content", "content marketing", "performance content",
    "affiliate content", "content specialist",
    "growth content", "ecommerce content", "b2b content",
    "content editor",
]
ROLE_TIER4 = [  # 15 pt — affiliate manager con componente editoriale
    "affiliate manager", "affiliate marketing manager", "partnership marketing",
    "affiliate program manager", "partner program manager",
    "partnerships manager",
]
ROLE_TIER5 = [  # 12 pt — senior editor/writer con crescita
    "senior editor", "senior writer", "senior content",
]

# Dimensione 2 — Fit settore (20 punti)
SECTOR_TIER1 = [  # 20 pt — eCommerce + affiliate
    "ecommerce", "e-commerce", "affiliate", "retail tech", "marketplace",
]
SECTOR_TIER2 = [  # 16 pt — SaaS / Tech
    "saas", "software", "technology", "platform", "developer", "api",
    "cloud", "enterprise software", "b2b tech",
]
SECTOR_TIER3 = [  # 14 pt — media digitale / publishing
    "media", "publishing", "news", "editorial", "magazine", "newsletter",
    "content platform", "digital media",
]
SECTOR_TIER4 = [  # 10 pt — fintech (no crypto)
    "fintech", "payments", "financial technology", "banking",
]
SECTOR_TIER5 = [  # 6 pt — healthcare, legal, education
    "health", "medical", "legal", "law firm", "education", "edtech",
]

# Dimensione 4 — Skill match (20 punti)
SKILL_STRONG = [  # skill di Marco forti
    "editorial", "content operations", "team management", "team lead",
    "hiring", "onboarding", "seo", "buying guide", "affiliate",
    "google analytics", "ga4", "awin", "wordpress", "content calendar",
    "content pipeline", "editorial planning", "quality standards",
    "search console", "seozoom",
]
SKILL_MEDIUM = [  # skill parziali
    "analytics", "data studio", "cms", "content strategy",
    "performance marketing", "link management", "partner tracking",
]
SKILL_GAP = [  # gap noti — colmabili ma riducono skill match
    "video production", "podcast", "motion graphic", "developer relations",
    "devrel", "paid social", "ppc", "paid media",
]

# Dimensione 5 — Colmabilità gap (10 punti)
CLOSABLE_KEYWORDS = [  # gap facilmente colmabili con supporto AI
    "b2b", "saas", "thought leadership", "insights", "data storytelling",
    "content distribution", "geo", "ai search", "generative",
    # email / newsletter
    "email marketing", "newsletter", "klaviyo", "mailchimp", "drip",
    # affiliate / partner platform
    "partner program", "affiliate platform", "impact", "shareasale", "rakuten",
    # inbound / growth
    "hubspot", "inbound marketing", "demand generation", "lead nurturing",
    # localization / multilingual
    "localization", "localisation", "multilingual", "translation management",
]
HARD_GAP_KEYWORDS = [  # gap strutturali — non colmabili rapidamente
    "video director", "podcast host", "motion design", "broadcast",
    "print production", "photojournalist",
]

# Dimensione 6 — Path di crescita (10 punti)
GROWTH_PATH_KEYWORDS = [  # indica traiettoria verso affiliate PM o head of content
    "affiliate program", "program management", "partnerships", "revenue",
    "head of", "director", "lead", "strategy", "ownership",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text(job: dict) -> str:
    """Testo combinato titolo + descrizione, lowercase."""
    title = job.get("title") or ""
    desc = job.get("description") or job.get("excerpt") or ""
    return (title + " " + desc).lower()


def _title(job: dict) -> str:
    return (job.get("title") or "").lower()


def _matches(text: str, keywords: list[str]) -> list[str]:
    return [kw for kw in keywords if kw in text]


def _salary_eur(job: dict) -> float | None:
    """Converte il salario in EUR approssimativo. Restituisce None se non dichiarato."""
    val = job.get("minSalary") or job.get("maxSalary")
    if not val:
        return None
    currency = (job.get("currency") or "USD").upper()
    rates = {"USD": 0.92, "GBP": 1.17, "EUR": 1.0, "CAD": 0.68, "AUD": 0.60}
    return float(val) * rates.get(currency, 0.92)


# ---------------------------------------------------------------------------
# Criteri eliminatori
# ---------------------------------------------------------------------------

def _is_location_compatible(job: dict) -> tuple[bool, str]:
    """
    Restituisce (compatibile, motivo).
    Logica conservativa: se ci sono restrizioni geografiche e nessuna
    indica compatibilità con l'Italia/EU, il ruolo è eliminatorio.

    - Nessuna restrizione → worldwide → ok
    - Almeno una restrizione compatibile (Europe, worldwide, Italy, ecc.) → ok
    - Solo restrizioni non-EU/non-worldwide → eliminatorio
    """
    restrictions = [loc.lower() for loc in job.get("locationRestrictions", [])]

    if not restrictions:
        return True, ""

    # Basta un segnale positivo per considerare il ruolo accessibile
    for loc in restrictions:
        for compatible in GEO_COMPATIBLE:
            if compatible in loc:
                return True, ""

    # Nessun segnale positivo → incompatibile (logica conservativa)
    return False, f"location non compatibile con Italia/EU: {', '.join(restrictions[:3])}"


def _check_eliminatory(job: dict, text: str) -> str | None:
    """Restituisce il motivo di eliminazione o None se ok."""
    title_low = _title(job)

    if _matches(text, GAMING_KEYWORDS):
        return "settore gaming"
    if _matches(text, CRYPTO_KEYWORDS):
        return "settore crypto/Web3"
    if _matches(title_low, ENTRY_LEVEL_KEYWORDS):
        return "ruolo entry level / internship"
    if _matches(text, NOT_REMOTE_KEYWORDS):
        return "non remote"

    compatible, reason = _is_location_compatible(job)
    if not compatible:
        return reason

    salary_eur = _salary_eur(job)
    if salary_eur is not None and salary_eur < 30_000:
        return f"salario troppo basso ({salary_eur:.0f} EUR)"

    return None


# ---------------------------------------------------------------------------
# Dimensioni di scoring
# ---------------------------------------------------------------------------

def _score_role(title: str) -> tuple[int, str]:
    if _matches(title, ROLE_TIER1):
        return 30, "editorial leadership con team ownership"
    if _matches(title, ROLE_TIER2):
        return 22, "content manager con ownership strategica"
    if _matches(title, ROLE_TIER3):
        return 18, "content marketing + SEO/performance"
    if _matches(title, ROLE_TIER4):
        return 15, "affiliate manager con componente editoriale"
    if _matches(title, ROLE_TIER5):
        return 12, "senior editor/writer con prospettiva crescita"
    return 5, "ruolo non allineato alla traiettoria"


def _score_sector(text: str) -> tuple[int, str]:
    # Settori a bassa priorità vanno verificati PRIMA per evitare
    # che keyword generiche (es. "editorial") li promuovano a tier3
    low_priority = _matches(text, SECTOR_TIER5)
    if low_priority and not _matches(text, SECTOR_TIER1 + SECTOR_TIER2):
        return 6, f"settore bassa priorità: {low_priority[0]}"

    if _matches(text, SECTOR_TIER1):
        return 20, "eCommerce / affiliate"
    if _matches(text, SECTOR_TIER2):
        return 16, "SaaS / Tech"
    if _matches(text, SECTOR_TIER3):
        return 14, "media / publishing"
    if _matches(text, SECTOR_TIER4):
        return 10, "fintech"
    if low_priority:
        return 6, "healthcare / legal / education"
    return 8, "settore non classificato"


def _score_salary(job: dict) -> tuple[int, str]:
    salary_eur = _salary_eur(job)
    if salary_eur is None:
        return 10, "salario non dichiarato"
    if salary_eur >= 50_000:
        return 20, f"salario nella fascia target ({salary_eur:.0f} EUR)"
    if salary_eur >= 40_000:
        return 14, f"salario accettabile ({salary_eur:.0f} EUR)"
    if salary_eur >= 30_000:
        return 4, f"salario sotto target ({salary_eur:.0f} EUR)"
    return 0, f"salario troppo basso ({salary_eur:.0f} EUR)"


def _score_skills(text: str) -> tuple[int, str]:
    strong = _matches(text, SKILL_STRONG)
    medium = _matches(text, SKILL_MEDIUM)
    gaps = _matches(text, SKILL_GAP)

    required_proxy = max(len(strong) + len(medium) + len(gaps), 1)
    raw = (len(strong) * 2 + len(medium)) / (required_proxy * 2)
    score = min(int(raw * 20), 20)

    detail = f"{len(strong)} skill forti, {len(medium)} parziali"
    if gaps:
        detail += f", gap: {', '.join(gaps[:2])}"
    return score, detail


def _score_closability(text: str) -> tuple[int, str]:
    closable = _matches(text, CLOSABLE_KEYWORDS)
    hard = _matches(text, HARD_GAP_KEYWORDS)

    if hard:
        return 2, f"gap strutturali rilevati: {', '.join(hard[:2])}"
    if closable:
        return 10, f"gap colmabili con supporto AI: {', '.join(closable[:2])}"
    return 6, "gap non determinabili dal testo"


def _score_growth(text: str) -> tuple[int, str]:
    hits = _matches(text, GROWTH_PATH_KEYWORDS)
    if len(hits) >= 3:
        return 10, "forte allineamento con traiettoria affiliate PM / head of content"
    if len(hits) >= 1:
        return 7, "parziale allineamento con traiettoria target"
    return 4, "path di crescita non evidente"


# ---------------------------------------------------------------------------
# Scorer principale
# ---------------------------------------------------------------------------

def score_job(job: dict) -> dict:
    text = _text(job)
    title = _title(job)

    eliminated_by = _check_eliminatory(job, text)

    if eliminated_by:
        return {
            "score": 10,
            "level": "Scartare",
            "strengths": [],
            "gaps": [f"Criterio eliminatorio: {eliminated_by}"],
            "action": "Scarta",
            "eliminated_by": eliminated_by,
            "title": job.get("title", "N/D"),
            "company": job.get("companyName", "N/D"),
            "salary": _fmt_salary(job),
            "location": _fmt_location(job),
            "link": job.get("applicationLink", ""),
            "pub_date": job.get("pubDate", ""),
            "guid": job.get("guid", ""),
        }

    role_pts, role_note = _score_role(title)
    sector_pts, sector_note = _score_sector(text)
    salary_pts, salary_note = _score_salary(job)
    skill_pts, skill_note = _score_skills(text)
    close_pts, close_note = _score_closability(text)
    growth_pts, growth_note = _score_growth(text)

    total = role_pts + sector_pts + salary_pts + skill_pts + close_pts + growth_pts

    if total >= 88:
        level = "Forte"
        action = "Candidati subito"
    elif total >= 72:
        level = "Buono"
        action = "Esplora"
    elif total >= 55:
        level = "Esplorare"
        action = "Monitora"
    else:
        level = "Scartare"
        action = "Scarta"

    strengths = [s for s in [role_note, sector_note, salary_note] if s]
    gaps = [g for g in [skill_note, close_note] if "gap" in g or "colmab" in g]

    return {
        "score": total,
        "level": level,
        "strengths": strengths[:3],
        "gaps": gaps[:2],
        "action": action,
        "eliminated_by": None,
        "title": job.get("title", "N/D"),
        "company": job.get("companyName", "N/D"),
        "salary": _fmt_salary(job),
        "location": _fmt_location(job),
        "link": job.get("applicationLink", ""),
        "pub_date": job.get("pubDate", ""),
        "guid": job.get("guid", ""),
    }


def _fmt_salary(job: dict) -> str:
    cur = job.get("currency", "USD")
    try:
        mn = float(job.get("minSalary") or 0) or None
        mx = float(job.get("maxSalary") or 0) or None
        if mn and mx:
            return f"{int(mn):,}–{int(mx):,} {cur}"
        if mn:
            return f"{int(mn):,}+ {cur}"
    except (ValueError, TypeError):
        pass
    return "n.d."


def _fmt_location(job: dict) -> str:
    locs = job.get("locationRestrictions", [])
    return ", ".join(locs) if locs else "Worldwide"
