"""
Unified ingestion runner for all connectorized cities in cities.yaml.

Phase 1 — Meeting calendar: scrape recent meetings for each city.
Phase 2 — Agenda items: extract structured agenda items from the first
           meeting with a details URL (Legistar only for now).

Usage:
  # All connectorized cities
  python run_all.py

  # Filter by connector type
  python run_all.py --connector civicplus
  python run_all.py --connector legistar

  # Single city (substring match on name)
  python run_all.py --city Artesia

  # Cap number of cities processed
  python run_all.py --connector civicplus --max-cities 10
"""

import argparse
import json
import sys
import traceback
from pathlib import Path

import yaml

from civic_scraper.connectors.civicplus import CivicPlusConnector
from civic_scraper.connectors.legistar import LegistarConnector

_CONFIG_PATH = Path(__file__).parent / "cities.yaml"
OUTPUT_ROOT = Path("data/processed")
PERIOD = "This Month"
FALLBACK_PERIOD = "Last Month"
MEETING_LIMIT = 5


def _safe(s: str) -> str:
    """Windows console may not support all Unicode — sanitize output strings."""
    encoding = sys.stdout.encoding or "utf-8"
    return s.encode(encoding, errors="replace").decode(encoding)


# ------------------------------------------------------------------
# City loading
# ------------------------------------------------------------------


def load_cities(connector_filter: str | None, city_filter: str | None) -> list[dict]:
    with _CONFIG_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    cities = []
    for entry in data.get("cities", []):
        if not entry.get("connector"):
            continue
        if connector_filter and entry["connector"] != connector_filter:
            continue
        if city_filter and city_filter.lower() not in entry["name"].lower():
            continue
        cities.append(entry)
    return cities


# ------------------------------------------------------------------
# Connector factory
# ------------------------------------------------------------------


def make_connector(entry: dict):
    connector = entry["connector"]
    name = entry["name"]

    if connector == "legistar":
        return LegistarConnector(
            jurisdiction=name,
            calendar_url=entry["legistar_url"],
            headless=True,
        )

    if connector == "civicplus":
        return CivicPlusConnector(
            jurisdiction=name,
            base_url=entry["civicplus_base_url"],
            body=entry.get("body") or "City Council",
            category_id=entry.get("civicplus_category_id"),
        )

    raise ValueError(f"Unknown connector: {connector!r}")


# ------------------------------------------------------------------
# Phase 1 helpers
# ------------------------------------------------------------------


def scrape_meetings(entry: dict, period: str) -> list:
    conn = make_connector(entry)
    body = entry.get("body") or "City Council"
    return conn.list_meetings(period=period, body=body, limit=MEETING_LIMIT)


def save_meetings(name: str, meetings: list, period_label: str) -> Path:
    slug = name.lower().replace(" ", "-")
    out_dir = OUTPUT_ROOT / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"meetings_{period_label}_sample.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump([m.to_dict() for m in meetings], f, indent=2)
    return out_path


# ------------------------------------------------------------------
# Phase 2 helpers  (Legistar only for now)
# ------------------------------------------------------------------


def extract_agenda(entry: dict, meeting: dict) -> list:
    conn = make_connector(entry)
    return conn.get_meeting_details(meeting["meeting_details_url"])


def save_agenda(name: str, meeting: dict, items: list) -> Path:
    slug = name.lower().replace(" ", "-")
    out_dir = OUTPUT_ROOT / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    date_slug = meeting["date"].replace("/", "-")
    out_path = out_dir / f"agenda_{date_slug}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump([i.to_dict() for i in items], f, indent=2)
    return out_path


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Ingest civic meeting data")
    parser.add_argument(
        "--connector",
        choices=["legistar", "civicplus"],
        help="Only run cities using this connector",
    )
    parser.add_argument(
        "--city", metavar="NAME", help="Only run cities whose name contains this string"
    )
    parser.add_argument(
        "--max-cities", type=int, metavar="N", help="Stop after processing N cities"
    )
    parser.add_argument(
        "--phase",
        type=int,
        choices=[1, 2],
        default=None,
        help="Run only phase 1 (calendar) or phase 2 (agenda items)",
    )
    args = parser.parse_args()

    cities = load_cities(args.connector, args.city)
    if args.max_cities:
        cities = cities[: args.max_cities]

    run_phase1 = args.phase in (None, 1)
    run_phase2 = args.phase in (None, 2)

    sep = "-" * 72

    # ---- Phase 1 ----
    if run_phase1:
        print(f"\n{sep}")
        print(f"Phase 1 - Calendar  (period='{PERIOD}', limit={MEETING_LIMIT})")
        connector_counts = {}
        for c in cities:
            connector_counts[c["connector"]] = connector_counts.get(c["connector"], 0) + 1
        summary = "  ".join(f"{k}:{v}" for k, v in connector_counts.items())
        print(f"Cities: {len(cities)}  [{summary}]")
        print(sep)
        print(f"{'City':<28} {'Connector':<10} {'Status':<6} {'Rows':<5} Notes")
        print(sep)

    city_results: dict[str, dict] = {}

    if run_phase1:
        for entry in cities:
            name = entry["name"]
            connector = entry["connector"]
            try:
                meetings = scrape_meetings(entry, PERIOD)
                period_label = "this_month"

                if not meetings or not any(m.meeting_details_url for m in meetings):
                    meetings = scrape_meetings(entry, FALLBACK_PERIOD)
                    period_label = "last_month"

                out_path = save_meetings(name, meetings, period_label)
                with_url = [m for m in meetings if m.meeting_details_url]
                city_results[name] = {"entry": entry, "meetings": meetings, "with_url": with_url}

                note = f"{len(with_url)} have URL"
                if period_label == "last_month":
                    note += f"  [fallback: '{FALLBACK_PERIOD}']"
                safe_name = _safe(name)
                print(f"{safe_name:<28} {connector:<10} {'OK':<6} {len(meetings):<5} {note}")
                print(f"{'':28}            -> {out_path}")

            except Exception as exc:
                city_results[name] = {"entry": entry, "meetings": [], "with_url": []}
                safe_name = _safe(name)
                print(f"{safe_name:<28} {connector:<10} {'FAIL':<6}       {exc}")
                traceback.print_exc()

    # ---- Phase 2 ----
    if run_phase2:
        legistar_cities = [c for c in cities if c["connector"] == "legistar"]
        if not legistar_cities:
            if run_phase2 and not run_phase1:
                print("No Legistar cities selected — Phase 2 skipped.")
        else:
            print(f"\n{sep}")
            print("Phase 2 - Agenda items  (first meeting with details URL, Legistar only)")
            print(sep)
            print(f"{'City':<28} {'Status':<6} {'Items':<6} Sample title")
            print(sep)

            for entry in legistar_cities:
                name = entry["name"]
                data = city_results.get(name, {})
                with_url = data.get("with_url", [])

                safe_name = _safe(name)

                if not with_url:
                    print(f"{safe_name:<28} {'SKIP':<6}        no meetings with details URL")
                    continue

                items, target = [], None
                for candidate in with_url:
                    try:
                        has_to_dict = hasattr(candidate, "to_dict")
                        candidate_dict = candidate.to_dict() if has_to_dict else candidate
                        result = extract_agenda(entry, candidate_dict)
                        if result:
                            items, target = result, candidate_dict
                            break
                    except Exception as exc:
                        skip_msg = f"skipping {candidate.date}: {exc}"
                        print(f"{safe_name:<28} {'WARN':<6}        {skip_msg}")

                if target is None:
                    print(f"{safe_name:<28} {'SKIP':<6}        all detail pages returned 0 items")
                else:
                    try:
                        out_path = save_agenda(name, target, items)
                        sample = items[0].title[:50] if items[0].title else "(no title)"
                        sample_safe = _safe(sample)
                        print(f"{safe_name:<28} {'OK':<6} {len(items):<6} {sample_safe!r}")
                        print(f"{'':28}         {target['date']} -> {out_path}")
                    except Exception as exc:
                        print(f"{safe_name:<28} {'FAIL':<6}        {exc}")
                        traceback.print_exc()

    print()


if __name__ == "__main__":
    main()
