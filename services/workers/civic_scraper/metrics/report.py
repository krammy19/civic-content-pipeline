"""Renders RunMetrics + drift flags into a human-readable Markdown health
report, suitable for a CI artifact - the thing a person actually reads
after a run, rather than a JSON file they'd have to diff by hand."""

from .collect import FIELD_TYPES, RunMetrics
from .drift import DriftFlag


def render_city_report(
    current: RunMetrics, baseline: RunMetrics | None, flags: list[DriftFlag]
) -> str:
    lines = [f"## {current.jurisdiction} — {current.run_id}", ""]
    lines.append(f"Generated: {current.generated_at}")
    lines.append("")

    if flags:
        lines.append(f"**{len(flags)} drift flag(s) — possible connector rot:**")
        lines.append("")
        for flag in flags:
            lines.append(f"- **{flag.metric}**: {flag.message}")
        lines.append("")
    elif baseline is not None:
        lines.append("No drift flags against the trailing baseline.")
        lines.append("")
    else:
        lines.append("No baseline yet — this is the first recorded run for this jurisdiction.")
        lines.append("")

    lines.append("| Metric | Current | Baseline |")
    lines.append("|---|---|---|")
    lines.append(
        f"| Rows parsed | {current.rows_parsed} | {baseline.rows_parsed if baseline else '—'} |"
    )
    lines.append(
        f"| Schema failure rate | {current.schema_failure_rate:.1%} | "
        f"{f'{baseline.schema_failure_rate:.1%}' if baseline else '—'} |"
    )
    for field_type in FIELD_TYPES:
        c = current.field_population_rates.get(field_type, 0.0)
        b = baseline.field_population_rates.get(field_type, 0.0) if baseline else None
        lines.append(
            f"| `{field_type}` population rate | {c:.1%} | {f'{b:.1%}' if b is not None else '—'} |"
        )
    lines.append(
        f"| Mean confidence | {current.mean_confidence:.3f} | "
        f"{f'{baseline.mean_confidence:.3f}' if baseline else '—'} |"
    )
    lines.append(
        f"| Hallucination rate | {current.hallucination_rate:.1%} | "
        f"{f'{baseline.hallucination_rate:.1%}' if baseline else '—'} |"
    )
    lines.append(
        f"| Review queue volume | {current.review_queue_volume} | "
        f"{baseline.review_queue_volume if baseline else '—'} |"
    )
    lines.append("")

    return "\n".join(lines)


def render_fleet_report(
    entries: list[tuple[RunMetrics, RunMetrics | None, list[DriftFlag]]],
) -> str:
    """A multi-city report - one section per jurisdiction that had a run,
    plus a one-line summary up top of which cities (if any) are flagged."""
    total_flags = sum(len(flags) for _, _, flags in entries)
    lines = ["# Extraction health report", ""]
    if total_flags:
        flagged = [current.jurisdiction for current, _, flags in entries if flags]
        lines.append(f"**{total_flags} drift flag(s)** across: {', '.join(flagged)}.")
    else:
        lines.append("No drift flags across any jurisdiction in this run.")
    lines.append("")

    for current, baseline, flags in entries:
        lines.append(render_city_report(current, baseline, flags))

    return "\n".join(lines)
