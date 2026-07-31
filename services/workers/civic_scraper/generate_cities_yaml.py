"""One-time script to generate cities.yaml from CA_city_websites_final.csv."""

import re
from pathlib import Path

import yaml

CSV_PATH = Path(r"C:\Users\m_noa\Downloads\CA_city_websites_final.csv")
OUT_PATH = Path(__file__).parent / "cities.yaml"

# Verified tested cities — override anything from CSV
VERIFIED = {
    "Oakland": {
        "platform": "legistar",
        "legistar_url": "https://oakland.legistar.com/calendar.aspx",
        "body": "Successor Agency and the City Council",
    },
    "Culver City": {
        "platform": "legistar",
        "legistar_url": "https://culver-city.legistar.com/Calendar.aspx",
        "body": "City Council Meeting Agenda",
    },
    "Mountain View": {
        "platform": "legistar",
        "legistar_url": "https://mountainview.legistar.com/Calendar.aspx",
        "body": "City Council",
    },
    "San Francisco": {
        "platform": "legistar",
        "legistar_url": "https://sfgov.legistar.com/Calendar.aspx",
        "body": "Board of Supervisors",
    },
    "Santa Clara": {
        "platform": "legistar",
        "legistar_url": "https://santaclara.legistar.com/Calendar.aspx",
        "body": "City Council and Authorities Concurrent",
    },
}

_LEGISTAR_RE = re.compile(r"https?://([^/]+\.legistar\.com)", re.IGNORECASE)


def legistar_calendar_url(raw_url: str) -> str:
    """Convert any legistar.com URL to its Calendar.aspx root."""
    m = _LEGISTAR_RE.match(raw_url)
    return f"https://{m.group(1)}/Calendar.aspx"


cities = []

with CSV_PATH.open(encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parts = line.split(",", 2)
        if len(parts) < 3:
            parts += [""] * (3 - len(parts))
        name, homepage, agenda_url = parts

        entry: dict = {"name": name, "homepage": homepage or None}

        if name in VERIFIED:
            entry.update(VERIFIED[name])
        elif _LEGISTAR_RE.search(agenda_url):
            entry["platform"] = "legistar"
            entry["legistar_url"] = legistar_calendar_url(agenda_url)
        else:
            entry["agenda_url"] = agenda_url or None

        cities.append(entry)


# Emit clean YAML — use block style for readability
class _Dumper(yaml.Dumper):
    pass


_Dumper.add_representer(
    type(None),
    lambda dumper, _: dumper.represent_scalar("tag:yaml.org,2002:null", ""),
)

with OUT_PATH.open("w", encoding="utf-8") as f:
    yaml.dump(
        {"cities": cities},
        f,
        Dumper=_Dumper,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )

print(f"Wrote {len(cities)} cities to {OUT_PATH}")
legistar_count = sum(1 for c in cities if c.get("platform") == "legistar")
print(f"  Legistar cities: {legistar_count}")
print(f"  Other cities:    {len(cities) - legistar_count}")
