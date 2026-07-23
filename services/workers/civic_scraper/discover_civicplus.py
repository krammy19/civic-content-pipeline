"""
Discovery pass for all CivicPlus cities in cities.yaml.

For each CivicPlus city:
  1. Derive base URL from homepage (scheme + host).
  2. GET /AgendaCenter and parse category checkboxes.
  3. Fuzzy-match target body (from 'body' field, default 'City Council').
  4. Record category_id + matched name, or a status code if it fails.

Adds to each CivicPlus city entry:
  civicplus_base_url    - confirmed base URL for AgendaCenter
  civicplus_category_id - matched category ID (if found)
  civicplus_category_name - actual category name matched
  civicplus_status      - ok | no_agenda_center | no_council_category | error

Updates cities.yaml in place. Safe to re-run — already-discovered cities are skipped.
"""
import sys
import yaml

# Windows console may not support all Unicode — sanitize output strings
def _safe(s: str) -> str:
    return s.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8")
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

CITIES_YAML = Path(__file__).parent / "cities.yaml"
MAX_WORKERS = 20
TIMEOUT = 10
_HEADERS = {"User-Agent": "Mozilla/5.0 (civic-engagement-app)"}


def _base_url(homepage: str) -> str:
    p = urlparse(homepage)
    return f"{p.scheme}://{p.netloc}"


def _discover_categories(base: str) -> dict[str, str]:
    r = requests.get(f"{base}/AgendaCenter", headers=_HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    cats: dict[str, str] = {}
    for cb in soup.find_all("input", {"name": "chkCategoryID"}):
        label = soup.find("label", {"for": cb.get("id")})
        if label:
            cats[label.get_text(strip=True).lower()] = cb["value"]
    return cats


def _match_category(cats: dict[str, str], target: str) -> tuple[str, str] | None:
    """Return (category_name, category_id) or None."""
    t = target.lower()
    if t in cats:
        return target, cats[t]
    for name, cid in cats.items():
        if t in name or name in t:
            return name, cid
    for name, cid in cats.items():
        if "council" in name:
            return name, cid
    return None


def probe_city(entry: dict) -> dict:
    result = dict(entry)

    # Skip if already probed
    if "civicplus_status" in entry:
        return result

    homepage = entry.get("homepage") or ""
    if not homepage:
        result["civicplus_status"] = "error"
        result["civicplus_note"] = "no homepage URL"
        return result

    base = _base_url(homepage)
    body = entry.get("body") or "City Council"

    try:
        cats = _discover_categories(base)
    except Exception as e:
        result["civicplus_status"] = "no_agenda_center"
        result["civicplus_note"] = str(e)[:120]
        return result

    if not cats:
        result["civicplus_status"] = "no_agenda_center"
        result["civicplus_note"] = "AgendaCenter returned no categories"
        return result

    match = _match_category(cats, body)
    if match is None:
        result["civicplus_status"] = "no_council_category"
        result["civicplus_note"] = f"categories found: {', '.join(cats.keys())}"
        return result

    matched_name, cid = match
    result["civicplus_base_url"] = base
    result["civicplus_category_id"] = cid
    result["civicplus_category_name"] = matched_name
    result["civicplus_status"] = "ok"
    return result


def _dump_yaml(data: dict, path: Path):
    class _Dumper(yaml.Dumper):
        pass
    _Dumper.add_representer(
        type(None),
        lambda d, _: d.represent_scalar("tag:yaml.org,2002:null", ""),
    )
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, Dumper=_Dumper, default_flow_style=False,
                  allow_unicode=True, sort_keys=False)


def main():
    with CITIES_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    cities: list[dict] = data["cities"]
    cp_cities = [c for c in cities if c.get("platform") == "civicplus"]
    pending = [c for c in cp_cities if "civicplus_status" not in c]

    print(f"CivicPlus cities: {len(cp_cities)}  |  Already probed: {len(cp_cities) - len(pending)}  |  To probe: {len(pending)}")
    print(f"Workers: {MAX_WORKERS}\n")

    updated: dict[str, dict] = {}
    done = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(probe_city, c): c["name"] for c in pending}
        for future in as_completed(futures):
            name = futures[future]
            done += 1
            try:
                result = future.result()
            except Exception as exc:
                print(f"  [{done:3d}/{len(pending)}] {name:<25} ERROR: {exc}", file=sys.stderr)
                updated[name] = next(c for c in pending if c["name"] == name)
                continue

            status = result.get("civicplus_status")
            cat_name = result.get("civicplus_category_name", "")
            cat_id = result.get("civicplus_category_id", "")

            if status == "ok":
                print(_safe(f"  [{done:3d}/{len(pending)}] {name:<25} OK      cat={cat_id:<4} '{cat_name}'"))
            else:
                note = result.get("civicplus_note", "")[:60]
                print(_safe(f"  [{done:3d}/{len(pending)}] {name:<25} {status:<22} {note}"))
            updated[name] = result

    # Merge back preserving original order
    by_name = {c["name"]: updated.get(c["name"], c) for c in cities}
    data["cities"] = [by_name[c["name"]] for c in cities]
    _dump_yaml(data, CITIES_YAML)

    # Summary
    all_cp = [by_name[c["name"]] for c in cp_cities]
    counts = Counter(c.get("civicplus_status") for c in all_cp)
    print(f"\n{'='*50}")
    print("Status breakdown:")
    for status, count in counts.most_common():
        print(f"  {status:<25} {count}")


if __name__ == "__main__":
    main()
