# Ingestion Pipeline

How meeting data actually gets from a municipal website onto disk as
normalized JSON today — the runners, their config, and the two phases
each one executes. This describes the current connector-based pipeline
only; the extraction/validation/digest stages in
[`SPEC.md`](../SPEC.md#3-target-architecture) are not built yet.

## Two phases, same shape everywhere

Both runners (`run_legistar.py`, the original single-platform script,
and `run_all.py`, the multi-connector successor) execute the same two
phases:

1. **Phase 1 — Calendar.** For each configured city, call
   `connector.list_meetings(period=..., body=..., limit=MEETING_LIMIT)`
   and write the result to
   `data/processed/<city-slug>/meetings_<period_label>_sample.json`.
   `PERIOD` defaults to `"This Month"`; if that returns nothing, or
   returns meetings where none have a `meeting_details_url` yet
   (common early in a month, before an agenda is published), the runner
   retries with `FALLBACK_PERIOD = "Last Month"` and labels the output
   accordingly.
2. **Phase 2 — Agenda items** (Legistar only, currently). For each city
   with at least one meeting that has a `meeting_details_url`, call
   `connector.get_meeting_details(url)` against candidates in order until
   one returns items, then write them to
   `data/processed/<city-slug>/agenda_<date-slug>.json`.

Both phases are best-effort per city: one city's failure (timeout,
unexpected markup, no meetings this period) is caught, logged, and does
not stop the run. `run_all.py` prints an `OK` / `FAIL` / `SKIP` status
line per city per phase so a run's outcome is scannable at a glance.

## `run_all.py` — the multi-connector runner

```bash
# Every connectorized city (Legistar + CivicPlus)
uv run python run_all.py

# Filter to one connector
uv run python run_all.py --connector civicplus
uv run python run_all.py --connector legistar

# Filter to one city (substring match on name)
uv run python run_all.py --city Artesia

# Cap how many cities get processed, e.g. for a quick smoke test
uv run python run_all.py --connector civicplus --max-cities 10

# Run only one phase
uv run python run_all.py --phase 1
uv run python run_all.py --phase 2
```

It reads every entry in `cities.yaml` that has a `connector:` field set,
constructs the matching connector class (`make_connector()` is the only
place that switches on connector type), and runs Phase 1 / Phase 2 as
described above.

## `run_legistar.py` — the original Legistar-only runner

Predates `run_all.py` and only drives `LegistarConnector`, but reads its
city list from the same `cities.yaml` (every entry with
`platform: legistar`, regardless of whether a full `connector:` block is
set). Kept because it's what the `.vscode/launch.json` debug
configuration points at.

## The city registry (`cities.yaml`)

Every city is one YAML entry. The fields present depend on how far that
city has gotten through the discovery pipeline described in
[`architecture.md`](architecture.md#platform-detection-and-the-city-registry):

```yaml
- name: Alhambra
  homepage: https://www.cityofalhambra.org/
  agenda_url: https://www.cityofalhambra.org/city-meetings
  platform: civicplus
  civicplus_base_url: https://www.cityofalhambra.org
  civicplus_category_id: '2'
  civicplus_category_name: City Council
  civicplus_status: ok
  connector: civicplus
```

A minimal, not-yet-connectorized entry can be as small as `name`,
`homepage`, and `agenda_url` — that's a city `detect_platforms.py`
hasn't resolved yet. `connector` is only set once a city has everything
its connector class needs to run without further discovery at scrape
time; `run_all.py` skips any entry without it.

## Output layout

```
data/processed/<slug>/
├── meetings_this_month_sample.json   # or meetings_last_month_sample.json on fallback
└── agenda_<mm-dd-yyyy>.json          # one per Phase-2 meeting, filename from meeting date
```

`<slug>` is the city name lowercased with spaces replaced by hyphens
(`"Culver City"` → `culver-city`). Each run **overwrites** the same
filename rather than appending or timestamping — there is no history of
past runs on disk, only the latest sample.

Watch the working directory when running either script: `OUTPUT_ROOT`
is the relative path `Path("data/processed")`, resolved against the
process's current working directory, not the repo root. Run from the
repo root and output lands in `data/processed/`; run from
`services/workers/` and it lands in `services/workers/data/processed/`
instead. Both locations currently exist in the repo for exactly this
reason — this is a known inconsistency, not a deliberate split.

## Running without installing the package

`civic_scraper` isn't installed as a package
([`pyproject.toml`](../pyproject.toml) sets `package = false`), so it
needs to be on `PYTHONPATH` explicitly:

```bash
PYTHONPATH=services/workers uv run python services/workers/civic_scraper/run_all.py
```

The checked-in `.vscode/launch.json` sets this automatically for the
"Run Legistar scraper" debug configuration, so breakpoints work without
exporting it by hand first.

## Example: why header-driven parsing matters

This constructs a `LegistarConnector` and feeds it a hand-built calendar
table directly — no network or browser involved — to show what
`_parse_meetings()` does with the header row before touching any cell
data. It's the same code path `list_meetings()` drives after Selenium
hands back a page source, and it's close to what
`tests/connectors/test_legistar.py::TestParseMeetings::test_minimal_column_layout_does_not_shift_fields`
actually asserts:

```python
connector = LegistarConnector(
    jurisdiction="Testville",
    calendar_url="https://testville.legistar.com/Calendar.aspx",
)

# A city that publishes none of the optional columns (no icon column,
# no Video, no Accessible*/Packet columns) — the layout that originally
# broke positional parsing (see docs/engineering-log.md).
html = calendar_table(
    headers=["Name", "Meeting Date", "Meeting Time", "Meeting Location"],
    rows=[["City Council", "12/31/2026", "CANCELLED", "Council Chambers"]],
)

meeting = connector._parse_meetings(html, body="City Council")[0]
assert meeting.date == "12/31/2026"  # not "" — the original bug's symptom
assert meeting.time == "CANCELLED"
assert meeting.location == "Council Chambers"
```
