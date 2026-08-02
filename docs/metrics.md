# Metrics and drift detection

This describes M6: per-run, per-city health metrics, and a trailing-
baseline comparison that flags "connector rot" — a city's platform
template changing underneath a connector in a way that degrades
extraction quality without anyone noticing until a resident does.

## What this is not

There is no gold set here, no hand-labeled ground truth, and this is
not the eval harness ([`docs/evals.md`](evals.md)). A gold-set eval
answers "is the model right, compared to a human's determination of the
truth." Drift detection answers a narrower, cheaper question: "did this
city's own numbers just change a lot compared to its own recent
history." It needs no labels at all — only a city's own past runs.
That's what makes it something you can run on every city, every run,
forever, where a gold set can only ever cover a hand-picked sample.

## What gets measured

`services/workers/civic_scraper/metrics/collect.py`'s `compute_run_metrics()`
summarizes one extraction run for one jurisdiction into a `RunMetrics`:

- **Rows parsed** — items that either validated or failed schema
  validation this run.
- **Schema failure rate** — the fraction that failed.
- **Field population rates** — for each of `motions`, `people`,
  `locations`, `amounts`: the fraction of *published* items with at
  least one fact of that type. A city whose `amounts` rate suddenly
  drops to zero is a city whose contracts stopped being extractable,
  not necessarily a city that stopped discussing money.
- **Mean confidence** and **hallucination rate** — computed from *raw*
  (pre-provenance-filter) extractions, for the same reason
  `evals/run_eval.py` scores raw output for these two numbers: the
  filtered output has already had its fabrications removed by
  construction, so scoring it would report 0% hallucination regardless
  of what the model actually did. `hallucination_rate` reuses
  `extraction.agenda_item.verify_provenance()` directly — the identical
  deterministic check M2 built for production filtering, not a
  reimplementation of it for monitoring purposes.
- **Review queue volume** — how many extractions this run sent to
  human review (see [`docs/review.md`](review.md)). A growing number
  here, independent of every other metric, is itself a leading
  indicator: extraction is having to hedge more, even before its
  accuracy visibly drops.

Persisted to `data/metrics/{jurisdiction-slug}/{run_id}.json` — one file
per run, gitignored (like `.cache/llm/` and `data/review_queue/`, this
is runtime observability data, not source).

## How drift is decided

`metrics/drift.py`'s `trailing_baseline()` averages every prior run
recorded for a jurisdiction — plain arithmetic mean, not a weighted or
decaying average, since there's no evidence yet that recent runs should
count more than older ones for a city that might only run monthly.
`detect_drift()` then compares the current run against that baseline
per metric, against a fixed absolute threshold:

| Metric | Threshold | Direction that triggers |
|---|---|---|
| Schema failure rate | 0.10 | Increase |
| Field population rate (per field) | 0.30 | Increase or decrease |
| Mean confidence | 0.15 | Decrease |
| Hallucination rate | 0.05 | Increase |

These are **absolute** deviations, not relative ones, and deliberately
loose. A field population rate swinging by 10 points from one meeting to
the next isn't unusual — a meeting with no contracts on the agenda isn't
"amounts extraction broke," it's "this meeting didn't have any
contracts." The thresholds are set to catch a real, sustained shift a
human should look at, not the ordinary variety of what municipal
agendas actually contain meeting to meeting. There is no statistical
basis for these exact numbers yet — they're a reasonable starting point
pending enough real run history to tune them against, the same honest
caveat every threshold in this project starts with (see
`docs/style-checking.md`'s sentence/paragraph ceilings for the same
kind of admission).

A jurisdiction's first run against `trailing_baseline()` returns `None`
— there is nothing to have drifted from yet, and `detect_drift()`
returns no flags rather than comparing against zero, which would flag
every single metric on every city's first-ever run.

## The health report

`metrics/report.py` renders `RunMetrics` + baseline + flags into
Markdown — `render_city_report()` for one jurisdiction,
`render_fleet_report()` for several concatenated with a one-line
summary of which cities (if any) are flagged. This is what
`.github/workflows/metrics.yml` uploads as a CI artifact: a person
reads this, not the underlying JSON.

## Live validation

`scripts/check_metrics_drift.py` is both the record of how this was
proven and a repeatable CI smoke test. It:

1. Extracts the same eight real June 9, 2026 San José agenda items
   `scripts/run_review_demo_batch.py` used for M4's review-queue demo
   (cached — this costs nothing after the first run) and computes a
   real `RunMetrics` from that output: `people` population 100%,
   `amounts` population 25%, mean confidence 0.855.
2. Saves that as the trailing history for a jurisdiction.
3. Builds a **deliberately simulated** broken-connector run: the exact
   same published items, with `people` and `amounts` facts stripped
   from every one — the way a connector reading the wrong table column
   after a platform redesign would silently produce empty fields
   without a single schema failure to show for it. This is simulated on
   purpose: proving "a broken connector triggers a drift flag" is not
   something to demonstrate by actually breaking a connector against a
   real city's site.
4. Runs `detect_drift()` against the trailing baseline.

**Real result:** `people` population rate moved from 100% to 0% — a
100-point swing, flagged. `amounts` moved from 25% to 0% — a 25-point
swing, and it was **not** flagged, because it falls under the 30-point
threshold. That's not a bug in the demo; it's the threshold doing
exactly what it's set to do, and it's worth stating plainly rather than
picking a threshold after the fact that would have flagged both: a field
that was already rarely populated dropping further is a weaker signal
than a field that was reliably populated collapsing to nothing. Whether
25 points on a field with a low baseline rate deserves its own,
lower-set threshold is an open question the current single flat
threshold doesn't try to answer — see Known limitations below.

## Known limitations

- **Thresholds are a starting guess, not derived from real drift data.**
  There isn't enough run history across enough cities yet to know what
  "normal" variance actually looks like per metric. The values above
  should be revisited once real, non-demo run history accumulates.
- **A flat threshold per field ignores each field's own baseline rate.**
  As the live validation above shows, a 25-point drop on a field with a
  25% baseline (going to zero) is arguably just as significant as a
  30-point drop on a field with an 80% baseline, but only the second is
  flagged today. A relative (percentage-of-baseline) threshold, or a
  per-field threshold, would catch this — not built because there's no
  real data yet to justify a specific alternative number over the
  current one.
- **The trailing baseline is an unweighted mean of all history.** A city
  with 50 recorded runs and one bad week won't show much movement in
  its baseline; a young city with 2 runs will see its baseline swing
  hard on run 3. A rolling window, or a minimum-history requirement
  before flagging at all, is the natural next step once real history
  exists to test either approach against.
- **Nothing here is wired into `run_all.py` yet.** `compute_run_metrics()`
  takes agenda items and raw extractions as arguments; nothing calls it
  automatically at the end of a real ingestion run. That's the same gap
  named throughout this project's README: every stage works standalone
  and has been run against real data, but no single runner chains stage
  to stage yet.
