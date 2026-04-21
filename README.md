# Job Search Agent

A rule-based job search agent that queries the [Himalayas](https://himalayas.app) public API, scores each listing against a custom rubric, and surfaces the best matches in the terminal.

Built as a personal tool and learning project — no LLM calls, no paid APIs, zero running cost.

---

## What it does

1. Queries Himalayas with 16 keyword sets (editorial, content marketing, affiliate, SEO, B2B content, newsletter...)
2. Deduplicates results and filters out expired listings
3. Scores each job across 6 dimensions (110 points total):
   - Role fit
   - Sector fit
   - Salary range
   - Skill match
   - Gap closability
   - Growth path alignment
4. Applies eliminatory filters (wrong geography, entry-level, crypto/gaming, too low salary)
5. Prints a ranked summary and optionally updates a local Markdown tracker

---

## Output example

```
============================================================
RISULTATI: 18 match su 241 offerte analizzate
============================================================

[ 95/110] █████████░░ FORTE
  Content Marketing Manager @ Federato
  Salario: 130,000–145,000 USD | Location: Worldwide
  Azione: Candidati subito
  + content manager con ownership strategica
  - gap colmabili con supporto AI: b2b, generative
  Link: https://himalayas.app/companies/federato/jobs/content-marketing-manager
```

---

## Setup

**Requirements:** Python 3.9+, `requests`

```bash
# Clone the repo
git clone https://github.com/marcostefanodoria81/job-search-agent.git
cd job-search-agent

# Install dependencies
pip install -r requirements.txt
```

No API key required.

---

## Usage

```bash
# Full run: score jobs + save JSON + update tracker
python main.py

# Dry run: score and print only, no files written
python main.py --dry-run
```

Results are saved to `results/YYYY-MM-DD.json`.

---

## Customizing for your profile

The scoring rubric is in `scorer.py`. Key things to adapt:

**Keywords and queries** (`sources.py`):
```python
QUERIES = [
    "editorial manager",
    "content lead",
    # add your own...
]
```

**Geography** (`scorer.py`):
```python
GEO_COMPATIBLE = [
    "worldwide", "anywhere", "europe", "eu", "emea",
    # add countries where you can work...
]
GEO_INCOMPATIBLE = [
    "us only", "canada only", "latam",
    # add regions to exclude...
]
```

**Role tiers** — edit `ROLE_TIER1` through `ROLE_TIER5` to match your target titles.

**Sector tiers** — edit `SECTOR_TIER1` through `SECTOR_TIER5` to weight your preferred industries.

---

## Scoring rubric

| Dimension | Max points |
|---|---|
| Role fit | 30 |
| Sector fit | 20 |
| Salary range | 20 |
| Skill match | 20 |
| Gap closability | 10 |
| Growth path | 10 |
| **Total** | **110** |

Thresholds: **Forte** ≥88 · **Buono** 72–87 · **Esplorare** 55–71 · **Scartare** <55

---

## Optional: tracker integration

The agent can append matches to a local Markdown file (`opportunities/tracker.md`).
This file is not included in the repo — it's a personal operations file.
If the file doesn't exist, the agent skips the update and prints a warning.

---

## Project structure

```
job-search-agent/
├── main.py          # Orchestrator
├── sources.py       # Himalayas API queries + expiry filter
├── scorer.py        # Rule-based scorer, 6 dimensions
├── scoring-rubric.md  # Human-readable rubric reference
├── requirements.txt
├── .env.example     # Template (no API key required currently)
└── results/         # Saved JSON results (gitignored)
```

---

## Notes

- Himalayas is a free public API — no authentication required
- The scorer is entirely rule-based (no LLM, no cost per run)
- The `results/` folder is gitignored: job data stays local
- Built with [Claude Code](https://claude.ai/code) as part of a learning project on AI-assisted workflows

---

## Author

Marco Doria — [LinkedIn](https://www.linkedin.com/in/marcostefanodoria/) · [marcostefanodoria81.github.io](https://marcostefanodoria81.github.io)
