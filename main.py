"""
Job Search Agent — Marco Doria
Fetches listings from multiple sources, scores them with a rule-based scorer, saves results.

Usage:
  python main.py           → full run: score jobs + save JSON + update tracker
  python main.py --dry-run → score and print only, no files written
"""

import argparse
import json
from datetime import date
from pathlib import Path

from sources import fetch_jobs
from scorer import score_job

# Percorsi relativi al workspace
RESULTS_DIR = Path(__file__).parent / "results"
TRACKER_PATH = Path(__file__).parent.parent / "opportunities" / "tracker.md"

LEVEL_PRIORITY = {"High": 0, "Medium": 1, "Low": 2}


def priority_label(score: int) -> str:
    if score >= 88:
        return "High"
    if score >= 72:
        return "Medium"
    return "Low"


def save_results(results: list[dict]) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    output_path = RESULTS_DIR / f"{date.today()}.json"
    try:
        output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    except OSError as e:
        print(f"WARNING: could not save JSON ({e}). Continuing anyway.")
        return output_path
    return output_path


def update_tracker(matches: list[dict]) -> None:
    """Appends listings with score ≥55 to the Pipeline section of the tracker."""
    if not matches:
        print("No matches to add to tracker.")
        return

    if not TRACKER_PATH.exists():
        print(f"WARNING: tracker not found at {TRACKER_PATH}. Use --dry-run or create the file.")
        return

    tracker = TRACKER_PATH.read_text()

    rows = []
    for r in matches:
        strengths_text = r["strengths"][0] if r["strengths"] else "—"
        gaps_text = r["gaps"][0] if r["gaps"] else "none"
        row = (
            f"| {r['company']} "
            f"| {r['title']} "
            f"| {r['salary']} "
            f"| {r['location']} "
            f"| Score {r['score']}/110 — {r['level']} "
            f"| {priority_label(r['score'])} "
            f"| {strengths_text}. Gaps: {gaps_text}. [Open]({r['link']}) |"
        )
        rows.append(row)

    marker = "| Company | Role | Salary | Location | Status | Priority | Notes |"
    separator = "|---------|------|--------|----------|--------|----------|-------|"

    if marker in tracker and separator in tracker:
        insert_after = f"{marker}\n{separator}"
        new_rows_block = "\n".join(rows)
        updated = tracker.replace(
            insert_after,
            f"{insert_after}\n{new_rows_block}",
            1,
        )
        TRACKER_PATH.write_text(updated)
        print(f"Tracker updated: {len(rows)} listings added.")
    else:
        print("WARNING: tracker structure not found. Manual update required.")


def print_summary(results: list[dict]) -> None:
    matches = [r for r in results if r["score"] >= 55]
    matches.sort(key=lambda x: x["score"], reverse=True)

    print(f"\n{'='*60}")
    print(f"RESULTS: {len(matches)} matches out of {len(results)} listings scored")
    print(f"{'='*60}")

    for r in matches:
        bar = "█" * (r["score"] // 10) + "░" * (11 - r["score"] // 10)
        print(f"\n[{r['score']:>3}/110] {bar} {r['level'].upper()}")
        print(f"  {r['title']} @ {r['company']}")
        print(f"  Salary: {r['salary']} | Location: {r['location']}")
        print(f"  Action: {r['action']}")
        if r["strengths"]:
            print(f"  + {r['strengths'][0]}")
        if r["gaps"]:
            print(f"  - {r['gaps'][0]}")
        if r["link"]:
            print(f"  Link: {r['link']}")

    discarded = len(results) - len(matches)
    if discarded:
        print(f"\n{discarded} listings discarded (score <55 or eliminatory filter).")


def main(dry_run: bool = False, with_linkedin: bool = False) -> None:
    print("Job Search Agent — starting\n")

    sources = "Himalayas, Remotive, RemoteOK, WWR" + (", LinkedIn" if with_linkedin else "")
    print(f"1/3 — Fetching listings from all sources ({sources})...")
    jobs = fetch_jobs(with_linkedin=with_linkedin)
    print(f"     {len(jobs)} unique listings found\n")

    print("2/3 — Scoring listings...")
    results = []
    for i, job in enumerate(jobs, 1):
        print(f"     [{i:>2}/{len(jobs)}] {job.get('title', '?')} @ {job.get('companyName', '?')}")
        scored = score_job(job)
        results.append(scored)

    print_summary(results)

    if not dry_run:
        print(f"\n3/3 — Saving results...")
        output_path = save_results(results)
        print(f"     JSON saved: {output_path}")
        matches = [r for r in results if r["score"] >= 55 and not r.get("eliminated_by")]
        update_tracker(matches)
    else:
        print("\n[dry-run] No files written, tracker not modified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job Search Agent — Marco Doria")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Score and print only, no files written and tracker not modified",
    )
    parser.add_argument(
        "--with-linkedin",
        action="store_true",
        help="Include LinkedIn via Apify (uses API credits — intended for scheduled runs)",
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run, with_linkedin=args.with_linkedin)
