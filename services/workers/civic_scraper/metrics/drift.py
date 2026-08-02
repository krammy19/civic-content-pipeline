"""
Compares a run's metrics against a trailing baseline - the mean of that
jurisdiction's own prior runs - and flags deviations beyond a threshold.
This is the actual "connector rot" signal: a city's platform changed its
template underneath the connector, or the extraction prompt regressed
for that city specifically, in a way that's visible in this city's own
numbers moving, independent of what any other city's numbers look like.

Thresholds are absolute, not relative, and deliberately loose. A city's
field population rates naturally vary meeting to meeting depending on
what was actually on that agenda - a meeting with no contracts on it
isn't "amounts extraction broke." These thresholds are set to catch a
real, sustained shift, not ordinary agenda-to-agenda variety.
"""

from dataclasses import dataclass

from .collect import FIELD_TYPES, RunMetrics

SCHEMA_FAILURE_RATE_THRESHOLD = 0.10
FIELD_POPULATION_RATE_THRESHOLD = 0.30
MEAN_CONFIDENCE_THRESHOLD = 0.15
HALLUCINATION_RATE_THRESHOLD = 0.05


@dataclass
class DriftFlag:
    metric: str
    baseline: float
    current: float
    delta: float
    message: str


def trailing_baseline(history: list[RunMetrics]) -> RunMetrics | None:
    """Mean of every prior run for one jurisdiction. None when there's no
    history yet - a first run has nothing to drift from, which is a
    fact worth being explicit about rather than comparing against zeros.
    """
    if not history:
        return None

    n = len(history)
    return RunMetrics(
        jurisdiction=history[0].jurisdiction,
        run_id="trailing-baseline",
        generated_at="",
        rows_parsed=round(sum(r.rows_parsed for r in history) / n),
        schema_failures=round(sum(r.schema_failures for r in history) / n),
        schema_failure_rate=sum(r.schema_failure_rate for r in history) / n,
        field_population_rates={
            field_type: sum(r.field_population_rates.get(field_type, 0.0) for r in history) / n
            for field_type in FIELD_TYPES
        },
        mean_confidence=sum(r.mean_confidence for r in history) / n,
        hallucination_rate=sum(r.hallucination_rate for r in history) / n,
        review_queue_volume=round(sum(r.review_queue_volume for r in history) / n),
    )


def detect_drift(current: RunMetrics, baseline: RunMetrics | None) -> list[DriftFlag]:
    if baseline is None:
        return []

    flags: list[DriftFlag] = []

    delta = current.schema_failure_rate - baseline.schema_failure_rate
    if delta > SCHEMA_FAILURE_RATE_THRESHOLD:
        flags.append(
            DriftFlag(
                "schema_failure_rate",
                baseline.schema_failure_rate,
                current.schema_failure_rate,
                delta,
                f"Schema failure rate rose from {baseline.schema_failure_rate:.1%} "
                f"to {current.schema_failure_rate:.1%}.",
            )
        )

    for field_type in FIELD_TYPES:
        b = baseline.field_population_rates.get(field_type, 0.0)
        c = current.field_population_rates.get(field_type, 0.0)
        if abs(c - b) > FIELD_POPULATION_RATE_THRESHOLD:
            flags.append(
                DriftFlag(
                    f"field_population_rate.{field_type}",
                    b,
                    c,
                    c - b,
                    f"'{field_type}' population rate moved from {b:.1%} to {c:.1%} - "
                    "a city template change is a likely cause.",
                )
            )

    delta = baseline.mean_confidence - current.mean_confidence
    if delta > MEAN_CONFIDENCE_THRESHOLD:
        flags.append(
            DriftFlag(
                "mean_confidence",
                baseline.mean_confidence,
                current.mean_confidence,
                -delta,
                f"Mean confidence dropped from {baseline.mean_confidence:.2f} "
                f"to {current.mean_confidence:.2f}.",
            )
        )

    delta = current.hallucination_rate - baseline.hallucination_rate
    if delta > HALLUCINATION_RATE_THRESHOLD:
        flags.append(
            DriftFlag(
                "hallucination_rate",
                baseline.hallucination_rate,
                current.hallucination_rate,
                delta,
                f"Hallucination rate rose from {baseline.hallucination_rate:.1%} "
                f"to {current.hallucination_rate:.1%}.",
            )
        )

    return flags
