"""
Job Search Agent — Marco Doria
Recupera offerte da Himalayas API, le valuta con uno scorer rule-based, salva i risultati.

Uso:
  python main.py           → ricerca completa + salva JSON + aggiorna tracker
  python main.py --dry-run → solo ricerca e scoring, non salva nulla
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

LEVEL_PRIORITY = {"Alta": 0, "Media": 1, "Bassa": 2}


def priority_label(score: int) -> str:
    if score >= 88:
        return "Alta"
    if score >= 72:
        return "Media"
    return "Bassa"


def save_results(results: list[dict]) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    output_path = RESULTS_DIR / f"{date.today()}.json"
    try:
        output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    except OSError as e:
        print(f"ATTENZIONE: impossibile salvare il JSON ({e}). Continuo comunque.")
        return output_path
    return output_path


def update_tracker(matches: list[dict]) -> None:
    """Aggiunge le offerte con score ≥55 alla sezione Pipeline del tracker."""
    if not matches:
        print("Nessun match da aggiungere al tracker.")
        return

    if not TRACKER_PATH.exists():
        print(f"ATTENZIONE: tracker non trovato in {TRACKER_PATH}. Usa --dry-run o crea il file.")
        return

    tracker = TRACKER_PATH.read_text()

    rows = []
    for r in matches:
        strengths_text = r["strengths"][0] if r["strengths"] else "—"
        gaps_text = r["gaps"][0] if r["gaps"] else "nessuno"
        row = (
            f"| {r['company']} "
            f"| {r['title']} "
            f"| {r['salary']} "
            f"| {r['location']} "
            f"| Score {r['score']}/110 — {r['level']} "
            f"| {priority_label(r['score'])} "
            f"| {strengths_text}. Gap: {gaps_text}. [Apri]({r['link']}) |"
        )
        rows.append(row)

    marker = "| Azienda | Ruolo | Range stimato | Location | Status | Priorità | Note |"
    separator = "|---------|-------|---------------|----------|--------|----------|------|"

    if marker in tracker and separator in tracker:
        insert_after = f"{marker}\n{separator}"
        new_rows_block = "\n".join(rows)
        updated = tracker.replace(
            insert_after,
            f"{insert_after}\n{new_rows_block}",
            1,
        )
        TRACKER_PATH.write_text(updated)
        print(f"Tracker aggiornato: {len(rows)} offerte aggiunte.")
    else:
        print("ATTENZIONE: struttura tracker non trovata. Aggiornamento manuale necessario.")


def print_summary(results: list[dict]) -> None:
    matches = [r for r in results if r["score"] >= 55]
    matches.sort(key=lambda x: x["score"], reverse=True)

    print(f"\n{'='*60}")
    print(f"RISULTATI: {len(matches)} match su {len(results)} offerte analizzate")
    print(f"{'='*60}")

    for r in matches:
        bar = "█" * (r["score"] // 10) + "░" * (11 - r["score"] // 10)
        print(f"\n[{r['score']:>3}/110] {bar} {r['level'].upper()}")
        print(f"  {r['title']} @ {r['company']}")
        print(f"  Salario: {r['salary']} | Location: {r['location']}")
        print(f"  Azione: {r['action']}")
        if r["strengths"]:
            print(f"  + {r['strengths'][0]}")
        if r["gaps"]:
            print(f"  - {r['gaps'][0]}")
        if r["link"]:
            print(f"  Link: {r['link']}")

    scartate = len(results) - len(matches)
    if scartate:
        print(f"\n{scartate} offerte scartate (score <55 o criterio eliminatorio).")


def main(dry_run: bool = False, with_linkedin: bool = False) -> None:
    print("Job Search Agent — avvio\n")

    fonti = "Himalayas, Remotive, RemoteOK, WWR" + (", LinkedIn" if with_linkedin else "")
    print(f"1/3 — Recupero offerte da tutte le fonti ({fonti})...")
    jobs = fetch_jobs(with_linkedin=with_linkedin)
    print(f"     Trovate {len(jobs)} offerte uniche\n")

    print("2/3 — Scoring offerte...")
    results = []
    for i, job in enumerate(jobs, 1):
        print(f"     [{i:>2}/{len(jobs)}] {job.get('title', '?')} @ {job.get('companyName', '?')}")
        scored = score_job(job)
        results.append(scored)

    print_summary(results)

    if not dry_run:
        print(f"\n3/3 — Salvo risultati...")
        output_path = save_results(results)
        print(f"     JSON salvato: {output_path}")
        matches = [r for r in results if r["score"] >= 55 and not r.get("eliminated_by")]
        update_tracker(matches)
    else:
        print("\n[dry-run] Nessun file scritto, tracker non modificato.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job Search Agent — Marco Doria")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Esegue scoring senza scrivere file né modificare il tracker",
    )
    parser.add_argument(
        "--with-linkedin",
        action="store_true",
        help="Include LinkedIn via Apify (consuma crediti — usare nel task automatizzato)",
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run, with_linkedin=args.with_linkedin)
