"""
Derives review/routing.py's per-field-type publish thresholds from
evals/baseline.json's calibration_by_field data.

    uv run python evals/derive_review_thresholds.py

Prior to this, review.DEFAULT_THRESHOLDS was a single hand-picked 0.9
applied to every field type, because M3's calibration baseline only
measured accuracy in aggregate - not broken out per field - and moving
individual thresholds without field-level data to justify it would have
looked more precise than it actually was (see docs/review.md). Now that
evals/run_eval.py computes a calibration curve per field
(metrics.calibration_points_by_field), an actual per-field threshold can
be derived instead of guessed.

The rule (metrics.derive_threshold_from_calibration): for each field
type, scanning from the least confident bucket upward, take the lower
edge of the first bucket whose measured accuracy clears TARGET_ACCURACY
- skipping any bucket with fewer than MIN_BUCKET_SIZE points as too
small to trust. If no bucket qualifies, keep FALLBACK (today's uniform
0.9) rather than invent a number the data doesn't support.

This is a reporting script, not something CI runs - re-run it by hand
whenever evals/baseline.json is updated, and manually decide whether to
copy its output into review/routing.py's DEFAULT_THRESHOLDS (see
docs/review.md for the currently-adopted values and the reasoning).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals import metrics  # noqa: E402

BASELINE_PATH = Path(__file__).resolve().parent / "baseline.json"

TARGET_ACCURACY = 0.9
MIN_BUCKET_SIZE = 10
FALLBACK = 0.9


def main() -> int:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    calibration_by_field = baseline.get("calibration_by_field")
    if not calibration_by_field:
        print(
            "No calibration_by_field in evals/baseline.json - "
            "run `civic eval --update-baseline` first."
        )
        return 1

    print(
        f"Target accuracy: {TARGET_ACCURACY:.0%}  |  "
        f"Minimum bucket size: {MIN_BUCKET_SIZE}  |  Fallback: {FALLBACK}\n"
    )

    for field in metrics.FIELD_TYPES:
        cal = calibration_by_field.get(field, {"buckets": []})
        buckets = [
            metrics.CalibrationBucket(b["range"], b["count"], b["mean_confidence"], b["accuracy"])
            for b in cal["buckets"]
        ]
        threshold, reason = metrics.derive_threshold_from_calibration(
            buckets,
            target_accuracy=TARGET_ACCURACY,
            min_bucket_size=MIN_BUCKET_SIZE,
            fallback=FALLBACK,
        )
        print(f"{field:<12} -> {threshold:<5} ({reason})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
