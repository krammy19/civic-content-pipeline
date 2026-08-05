"""
Thin argparse wrapper exposing every already-built pipeline stage as one
installed console command, `civic` (see `[project.scripts]` in
pyproject.toml). No business logic lives here - every subcommand parses
its own arguments and calls straight into the module already
responsible for that stage. See docs/ingestion-pipeline.md and the
per-milestone docs (docs/evals.md, docs/review.md,
docs/style-checking.md, docs/metrics.md) for what each stage actually
does; this module exists only so a fresh clone can run

    uv run civic ingest --city "San Jose"

instead of needing a `PYTHONPATH=services/workers` prefix and knowing
which script under `services/workers/civic_scraper/` to invoke.
"""

import argparse
import json
import sys

from .paths import REPO_ROOT


def _cmd_ingest(argv: list[str]) -> int:
    from . import run_all

    return run_all.main(argv) or 0


def _cmd_review(argv: list[str]) -> int:  # noqa: ARG001 - review's CLI takes no arguments today
    from .review import cli as review_cli

    return review_cli.main()


def _cmd_extract(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="civic extract")
    parser.add_argument(
        "item_file",
        help=(
            "JSON file with item_title, item_number, source_document, "
            "and document_text - the same shape as one evals/gold/*.json "
            "case's own fields."
        ),
    )
    parser.add_argument("--model", default=None, help="Override the default extraction model")
    args = parser.parse_args(argv)

    from .extraction.agenda_item import DEFAULT_MODEL, extract_agenda_item

    with open(args.item_file, encoding="utf-8") as f:
        spec = json.load(f)

    item = extract_agenda_item(
        item_title=spec["item_title"],
        item_number=spec.get("item_number"),
        source_document=spec["source_document"],
        document_text=spec["document_text"],
        model=args.model or DEFAULT_MODEL,
    )
    print(item.model_dump_json(indent=2))
    return 0


def _cmd_digest(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="civic digest")
    parser.add_argument(
        "meeting_file",
        help=(
            "JSON file with a serialized Meeting - agenda_items should "
            "already be confidence-routed."
        ),
    )
    args = parser.parse_args(argv)

    from .digest.generate_digest import generate_digest
    from .models import Meeting

    with open(args.meeting_file, encoding="utf-8") as f:
        meeting = Meeting.model_validate_json(f.read())

    print(generate_digest(meeting=meeting))
    return 0


def _cmd_check(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="civic check")
    parser.add_argument("digest_file", help="Path to a generated digest (Markdown).")
    parser.add_argument(
        "--context-file",
        help=(
            "Optional JSON with known_item_numbers (list) and people (list of "
            "{raw_name, role}) for citation/title checks. Without it, citation-"
            "validity and first-reference-title checks are skipped, not failed."
        ),
    )
    parser.add_argument(
        "--facts-file",
        help=(
            "Optional path to the rendered facts block, for the judge "
            "tier's unsupported-claim check."
        ),
    )
    args = parser.parse_args(argv)

    sys.path.insert(0, str(REPO_ROOT))
    from checks.style_check import StyleContext, check_deterministic, judge_style

    with open(args.digest_file, encoding="utf-8") as f:
        digest = f.read()

    context = StyleContext()
    if args.context_file:
        with open(args.context_file, encoding="utf-8") as f:
            raw = json.load(f)
        context = StyleContext(
            known_item_numbers=set(raw.get("known_item_numbers", [])),
            people=raw.get("people", []),
        )

    facts_block = ""
    if args.facts_file:
        with open(args.facts_file, encoding="utf-8") as f:
            facts_block = f.read()

    findings = check_deterministic(digest, context)
    findings += judge_style(digest_markdown=digest, facts_block=facts_block)

    if not findings:
        print("No findings.")
    for finding in findings:
        print(f"[{finding.severity:<6}] {finding.rule}: {finding.message}")

    return 1 if any(f.severity == "high" for f in findings) else 0


def _cmd_eval(argv: list[str]) -> int:
    sys.path.insert(0, str(REPO_ROOT / "services" / "workers"))
    sys.path.insert(0, str(REPO_ROOT))
    from evals import run_eval

    return run_eval.main(argv)


def _cmd_run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="civic run")
    parser.add_argument(
        "--city",
        required=True,
        help="City name substring from cities.yaml - must use the legistar connector",
    )
    parser.add_argument(
        "--meeting",
        required=True,
        help="Substring to match against a meeting's date, e.g. '12/09/2025'",
    )
    parser.add_argument("--model", default=None, help="Override the default extraction model")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve the meeting and print the plan without calling the extraction API",
    )
    args = parser.parse_args(argv)

    sys.path.insert(0, str(REPO_ROOT))
    sys.path.insert(0, str(REPO_ROOT / "services" / "workers"))
    from .extraction.agenda_item import DEFAULT_MODEL
    from .runner import RunOutcome, StageError
    from .runner import run as run_pipeline

    try:
        outcome = run_pipeline(
            city=args.city,
            meeting_selector=args.meeting,
            model=args.model or DEFAULT_MODEL,
            dry_run=args.dry_run,
        )
    except StageError as exc:
        print(f"\nRUN FAILED at stage '{exc.stage}': {exc.cause}")
        return 1

    if not isinstance(outcome, RunOutcome):
        print("\nDry run - nothing was published or spent:")
        print(json.dumps(outcome, indent=2))
        return 0

    print("\n--- Digest ---")
    print(outcome.digest)
    high = [f for f in outcome.style_findings if f.severity == "high"]
    print(f"\nStyle findings: {len(outcome.style_findings)} ({len(high)} high-severity)")
    print(f"Metrics written to {outcome.metrics_path}")
    return 1 if high else 0


def _cmd_metrics(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="civic metrics")
    parser.add_argument("--city", required=True, help="Jurisdiction name, e.g. 'San Jose'")
    args = parser.parse_args(argv)

    from .metrics.drift import detect_drift, trailing_baseline
    from .metrics.report import render_city_report
    from .metrics.store import load_run_history

    history = load_run_history(args.city)
    if not history:
        print(f"No recorded runs for {args.city!r} under data/metrics/.")
        return 0

    current = history[-1]
    baseline = trailing_baseline(history[:-1])
    flags = detect_drift(current, baseline)
    print(render_city_report(current, baseline, flags))
    return 0


_COMMANDS = {
    "ingest": _cmd_ingest,
    "review": _cmd_review,
    "extract": _cmd_extract,
    "digest": _cmd_digest,
    "check": _cmd_check,
    "eval": _cmd_eval,
    "metrics": _cmd_metrics,
    "run": _cmd_run,
}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if not argv or argv[0] in ("-h", "--help"):
        print("usage: civic <command> [args]")
        print(f"commands: {', '.join(_COMMANDS)}")
        print("Run `civic <command> --help` for a command's own arguments.")
        return 0

    command, rest = argv[0], argv[1:]
    handler = _COMMANDS.get(command)
    if handler is None:
        print(f"Unknown command: {command!r}. Commands: {', '.join(_COMMANDS)}")
        return 1

    return handler(rest)


if __name__ == "__main__":
    raise SystemExit(main())
