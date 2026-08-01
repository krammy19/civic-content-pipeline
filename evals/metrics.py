"""
Pure scoring functions for the eval harness.

No network calls and no civic_scraper/Pydantic imports - everything here
operates on plain dicts, so it's fully covered by tests/evals/test_metrics.py
using synthetic fixtures alone. evals/run_eval.py is what turns real
extraction output into the shapes these functions expect; docs/evals.md
explains the methodology and its known limitations in prose.

Two different predictions get scored against the same gold case, on
purpose, because they answer different questions:

  - Precision/recall/F1 are computed against the FILTERED (production)
    output - what a caller of extract_agenda_item() actually receives,
    after unverified extractions are already dropped.
  - Hallucination rate and calibration are computed against the RAW
    (pre-filter) output - what the model actually said before the
    provenance check removed the fabrications. Scoring hallucination
    rate on already-filtered output would trivially read 0% every time,
    since filtering exists specifically to remove exactly those cases.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher

FIELD_TYPES = ("motions", "people", "locations", "amounts")

# Motion matching intentionally does not cross-check moved_by/seconded_by
# identity - only outcome and tally/text similarity. A model that gets the
# right outcome with the wrong mover would still count as a match today.
# See docs/evals.md's methodology section for why, and what a v2 matcher
# would need.


def normalize(text: str | None) -> str:
    return " ".join((text or "").lower().split())


def similarity(a: str | None, b: str | None) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def match_motion(gold: dict, pred: dict, text_threshold: float = 0.5) -> bool:
    if gold.get("outcome") != pred.get("outcome"):
        return False
    gold_tally, pred_tally = gold.get("tally"), pred.get("tally")
    if gold_tally and pred_tally and normalize(gold_tally) == normalize(pred_tally):
        return True
    return similarity(gold.get("text"), pred.get("text")) >= text_threshold


# Titles the model sometimes fuses into raw_name depending on grammatical
# context - "Vice Mayor Pam Foley motioned" gets extracted as bare "Pam
# Foley", but "co-authored by Mayor Mahan, Councilmember Tordillos" (a
# comma-separated list where title+name reads as one unit) gets extracted
# with the title still attached. Both are defensible readings of "exactly
# as written" - stripping the title before comparing means gold doesn't
# have to guess which form a given sentence will produce.
_PERSON_TITLES = (
    "vice mayor",
    "mayor",
    "council member",
    "councilmember",
    "commissioner",
    "deputy director",
    "director",
    "chair",
    "vice chair",
)


def _strip_title(name: str | None) -> str:
    normalized = normalize(name)
    for title in _PERSON_TITLES:
        if normalized.startswith(title + " "):
            return normalized[len(title) + 1 :]
    return normalized


def match_person(gold: dict, pred: dict, threshold: float = 0.8) -> bool:
    a, b = _strip_title(gold.get("raw_name")), _strip_title(pred.get("raw_name"))
    return SequenceMatcher(None, a, b).ratio() >= threshold


def match_location(gold: dict, pred: dict, threshold: float = 0.5) -> bool:
    return similarity(gold.get("raw_text"), pred.get("raw_text")) >= threshold


def _amounts_equal(a, b) -> bool:
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) < 0.01
    except (TypeError, ValueError):
        return False


def match_amount(gold: dict, pred: dict, threshold: float = 0.5) -> bool:
    """When both sides have a parsed amount_usd, that's authoritative - a
    numeric mismatch is a real mismatch, full stop. Falling through to text
    similarity in that case would incorrectly match "$1,000,000" against
    "$2,000,000" (they share every character except one digit). Text
    similarity is only the fallback when a numeric value is missing on
    either side.
    """
    gold_amount, pred_amount = gold.get("amount_usd"), pred.get("amount_usd")
    if gold_amount is not None and pred_amount is not None:
        return _amounts_equal(gold_amount, pred_amount)
    return similarity(gold.get("raw_text"), pred.get("raw_text")) >= threshold


MATCHERS = {
    "motions": match_motion,
    "people": match_person,
    "locations": match_location,
    "amounts": match_amount,
}


@dataclass
class MatchResult:
    tp_pairs: list[tuple[int, int]]
    unmatched_gold: list[int]
    unmatched_pred: list[int]


def greedy_match(gold_list: list[dict], pred_list: list[dict], match_fn) -> MatchResult:
    """Greedy one-to-one matching: each gold item claims the first
    still-unclaimed prediction satisfying match_fn, in gold-list order.

    Not a globally-optimal bipartite matching, but simple, deterministic,
    and good enough at this gold-set's size (a handful of facts per
    field per case, not hundreds).
    """
    matched_pred: set[int] = set()
    tp_pairs: list[tuple[int, int]] = []

    for gi, g in enumerate(gold_list):
        for pi, p in enumerate(pred_list):
            if pi in matched_pred:
                continue
            if match_fn(g, p):
                matched_pred.add(pi)
                tp_pairs.append((gi, pi))
                break

    matched_gold = {gi for gi, _ in tp_pairs}
    unmatched_gold = [i for i in range(len(gold_list)) if i not in matched_gold]
    unmatched_pred = [i for i in range(len(pred_list)) if i not in matched_pred]
    return MatchResult(tp_pairs, unmatched_gold, unmatched_pred)


@dataclass
class FieldScore:
    field: str
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float


def score_field(field: str, gold_list: list[dict], pred_list: list[dict]) -> FieldScore:
    """Precision/recall/F1 for one field type in one case.

    Convention for the empty-set edge cases (matches sklearn's
    zero_division=1 behavior): precision is 1.0 when nothing was
    predicted (nothing to be wrong about), recall is 1.0 when there was
    nothing to find. A false negative (gold exists, nothing predicted)
    still correctly drives recall - and therefore F1 - to 0.
    """
    match_fn = MATCHERS[field]
    result = greedy_match(gold_list, pred_list, match_fn)
    tp = len(result.tp_pairs)
    fp = len(result.unmatched_pred)
    fn = len(result.unmatched_gold)

    precision = 1.0 if (tp + fp) == 0 else tp / (tp + fp)
    recall = 1.0 if (tp + fn) == 0 else tp / (tp + fn)
    f1 = 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)

    return FieldScore(field, tp, fp, fn, precision, recall, f1)


def is_verified(raw_extracted: dict, document_text: str) -> bool:
    """Mirrors civic_scraper.extraction.agenda_item.verify_provenance() on a
    plain dict, so this module has no civic_scraper/Pydantic dependency."""
    return raw_extracted["provenance"]["source_text"] in document_text


@dataclass
class CaseEvaluation:
    case_id: str
    field_scores: dict[str, FieldScore]
    hallucinated: int
    total_raw_extractions: int
    calibration_points: list[tuple[float, bool]]  # (confidence, was_correct)


def evaluate_case(
    case_id: str,
    gold: dict[str, list[dict]],
    raw_predictions: dict[str, list[dict]],
    filtered_predictions: dict[str, list[dict]],
    document_text: str,
) -> CaseEvaluation:
    """Score one case against both its raw and filtered predictions.

    gold[field] entries are plain value dicts (e.g. {"raw_name": ...,
    "role": ..., "source_text": ...}). raw_predictions[field] and
    filtered_predictions[field] entries are Extracted[T]-shaped dicts
    ({"value": {...}, "confidence": float, "provenance": {...}}), i.e.
    AgendaItem.model_dump() output.
    """
    field_scores: dict[str, FieldScore] = {}
    hallucinated = 0
    total_raw = 0
    calibration_points: list[tuple[float, bool]] = []

    for field in FIELD_TYPES:
        gold_facts = gold.get(field, [])
        raw_facts = raw_predictions.get(field, [])
        filtered_facts = filtered_predictions.get(field, [])

        filtered_values = [f["value"] for f in filtered_facts]
        field_scores[field] = score_field(field, gold_facts, filtered_values)

        match_fn = MATCHERS[field]
        for raw_fact in raw_facts:
            total_raw += 1
            verified = is_verified(raw_fact, document_text)
            if not verified:
                hallucinated += 1
            matched = any(match_fn(g, raw_fact["value"]) for g in gold_facts)
            calibration_points.append((raw_fact["confidence"], verified and matched))

    return CaseEvaluation(case_id, field_scores, hallucinated, total_raw, calibration_points)


@dataclass
class AggregateFieldScore:
    field: str
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float


def aggregate_field_scores(evaluations: list[CaseEvaluation]) -> dict[str, AggregateFieldScore]:
    """Pool true/false positives/negatives across all cases before computing
    precision/recall/F1 - not a per-case average, which would weight a
    case with one gold fact the same as a case with ten."""
    totals = {f: {"tp": 0, "fp": 0, "fn": 0} for f in FIELD_TYPES}
    for ev in evaluations:
        for field, score in ev.field_scores.items():
            totals[field]["tp"] += score.true_positives
            totals[field]["fp"] += score.false_positives
            totals[field]["fn"] += score.false_negatives

    result: dict[str, AggregateFieldScore] = {}
    for field, t in totals.items():
        tp, fp, fn = t["tp"], t["fp"], t["fn"]
        precision = 1.0 if (tp + fp) == 0 else tp / (tp + fp)
        recall = 1.0 if (tp + fn) == 0 else tp / (tp + fn)
        f1 = 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)
        result[field] = AggregateFieldScore(field, tp, fp, fn, precision, recall, f1)
    return result


def aggregate_hallucination_rate(evaluations: list[CaseEvaluation]) -> float:
    total_hallucinated = sum(e.hallucinated for e in evaluations)
    total_raw = sum(e.total_raw_extractions for e in evaluations)
    return 0.0 if total_raw == 0 else total_hallucinated / total_raw


def schema_validity_rate(successes: int, total: int) -> float:
    return 1.0 if total == 0 else successes / total


# Confidence buckets for calibration reporting. Deliberately coarse (five
# buckets, not ten) - the gold set has a few hundred raw extractions at
# most, and finer buckets would mostly report on 1-2 points each.
CALIBRATION_BUCKETS = [(0.0, 0.5), (0.5, 0.7), (0.7, 0.85), (0.85, 0.95), (0.95, 1.01)]


@dataclass
class CalibrationBucket:
    range_label: str
    count: int
    mean_confidence: float
    accuracy: float


def compute_calibration(
    points: list[tuple[float, bool]],
) -> tuple[list[CalibrationBucket], float]:
    """Bucket (confidence, was_correct) points and compare stated confidence
    against actual accuracy per bucket.

    Returns (buckets, expected_calibration_error). ECE is the count-weighted
    mean absolute gap between mean confidence and accuracy across buckets -
    0.0 is perfectly calibrated, higher means the model's confidence
    doesn't track its actual correctness rate. A model that states 0.9
    confidence but is right 60% of the time is overconfident; this number
    is how you'd notice.
    """
    buckets: list[CalibrationBucket] = []
    total = len(points)
    weighted_gap_sum = 0.0

    for low, high in CALIBRATION_BUCKETS:
        bucket_points = [(c, ok) for c, ok in points if low <= c < high]
        label = f"[{low:.2f}, {high:.2f})"
        if not bucket_points:
            buckets.append(CalibrationBucket(label, 0, 0.0, 0.0))
            continue
        mean_conf = sum(c for c, _ in bucket_points) / len(bucket_points)
        accuracy = sum(1 for _, ok in bucket_points if ok) / len(bucket_points)
        buckets.append(CalibrationBucket(label, len(bucket_points), mean_conf, accuracy))
        weighted_gap_sum += abs(mean_conf - accuracy) * len(bucket_points)

    ece = 0.0 if total == 0 else weighted_gap_sum / total
    return buckets, ece


def mean_confidence(points: list[tuple[float, bool]]) -> float:
    return 0.0 if not points else sum(c for c, _ in points) / len(points)
