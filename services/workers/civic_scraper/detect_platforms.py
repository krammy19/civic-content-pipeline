"""
Detect the agenda-hosting platform for each city in cities.yaml.

Strategy per unconfirmed city:
  1. Probe agenda_url: follow redirects, scan final URL + HTML for platform signatures.
  2. If still unknown, try common Legistar subdomain slug patterns via HEAD request.

Updates cities.yaml in place. Safe to re-run — already-confirmed cities are skipped.
"""
import re
import sys
import yaml
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

CITIES_YAML = Path(__file__).parent / "cities.yaml"

REQUEST_TIMEOUT = 8       # seconds for agenda URL probe
LEGISTAR_TIMEOUT = 5      # seconds for subdomain HEAD probe
MAX_WORKERS = 20
HTML_SCAN_BYTES = 60_000

PLATFORM_PATTERNS: dict[str, list[str]] = {
    "legistar":    [r"legistar\.com"],
    "granicus":    [r"granicus\.com"],
    "civicplus":   [r"civicplus\.com", r"civicplusmedia\.com"],
    "primegov":    [r"primegov\.com"],
    "civicclerk":  [r"civicclerk\.com"],
    "boarddocs":   [r"boarddocs\.com"],
    "novusagenda": [r"novusagenda\.com"],
    "iqm2":        [r"iqm2\.com"],
}

_HEADERS = {"User-Agent": "Mozilla/5.0 (civic-engagement-app platform detector)"}


def _legistar_slugs(city_name: str) -> list[str]:
    name = city_name.lower().strip()
    no_sp = name.replace(" ", "")
    hyphen = name.replace(" ", "-")
    return [no_sp, hyphen, no_sp + "ca", hyphen + "-ca"]


def _extract_legistar_base(text: str) -> str | None:
    m = re.search(r"https?://([a-z0-9-]+\.legistar\.com)", text, re.IGNORECASE)
    return f"https://{m.group(1)}/Calendar.aspx" if m else None


def _detect_platform(text: str) -> str | None:
    for platform, patterns in PLATFORM_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                return platform
    return None


def _probe_agenda_url(url: str) -> tuple[str, str] | None:
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True,
                            headers=_HEADERS)
        return resp.url, resp.text[:HTML_SCAN_BYTES]
    except Exception:
        return None


def _probe_legistar_subdomain(city_name: str) -> str | None:
    for slug in _legistar_slugs(city_name):
        url = f"https://{slug}.legistar.com/Calendar.aspx"
        try:
            resp = requests.head(url, timeout=LEGISTAR_TIMEOUT, allow_redirects=True,
                                 headers=_HEADERS)
            if resp.status_code == 200 and "legistar.com" in resp.url.lower():
                m = re.match(r"https?://[^/]+\.legistar\.com", resp.url, re.IGNORECASE)
                return (m.group(0) + "/Calendar.aspx") if m else url
        except Exception:
            pass
    return None


def detect_city(entry: dict) -> dict:
    if entry.get("platform"):
        return entry

    name = entry["name"]
    result = dict(entry)

    # Step 1 — probe existing agenda_url
    agenda_url = entry.get("agenda_url")
    if agenda_url:
        probe = _probe_agenda_url(agenda_url)
        if probe:
            final_url, html = probe
            corpus = final_url + "\n" + html
            platform = _detect_platform(corpus)
            if platform:
                result["platform"] = platform
                if platform == "legistar":
                    result["legistar_url"] = _extract_legistar_base(corpus) or _extract_legistar_base(final_url)
                    result.pop("agenda_url", None)
                return result

    # Step 2 — Legistar subdomain brute-force
    legistar_url = _probe_legistar_subdomain(name)
    if legistar_url:
        result["platform"] = "legistar"
        result["legistar_url"] = legistar_url
        result.pop("agenda_url", None)

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
    pending = [c for c in cities if not c.get("platform")]
    already_known = len(cities) - len(pending)

    print(f"Cities total:     {len(cities)}")
    print(f"Already confirmed:{already_known}")
    print(f"To probe:         {len(pending)}")
    print(f"Workers:          {MAX_WORKERS}\n")

    results: dict[str, dict] = {}
    newly_found = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(detect_city, c): c["name"] for c in pending}
        done = 0
        for future in as_completed(futures):
            name = futures[future]
            done += 1
            try:
                result = future.result()
            except Exception as exc:
                print(f"  [{done:3d}/{len(pending)}] {name:<25} ERROR: {exc}", file=sys.stderr)
                results[name] = next(c for c in pending if c["name"] == name)
                continue

            platform = result.get("platform")
            if platform:
                newly_found += 1
                extra = result.get("legistar_url") or ""
                print(f"  [{done:3d}/{len(pending)}] {name:<25} -> {platform:<12} {extra}")
            else:
                print(f"  [{done:3d}/{len(pending)}] {name:<25} -> (unknown)")
            results[name] = result

    # Merge back preserving original order
    updated_cities = [results.get(c["name"], c) for c in cities]
    data["cities"] = updated_cities
    _dump_yaml(data, CITIES_YAML)

    total_confirmed = sum(1 for c in updated_cities if c.get("platform"))
    print(f"\nDone. Newly detected: {newly_found}  |  Total confirmed: {total_confirmed}/{len(cities)}")
    counts = Counter(c.get("platform") for c in updated_cities if c.get("platform"))
    for platform, count in counts.most_common():
        print(f"  {platform:<15} {count}")


if __name__ == "__main__":
    main()
