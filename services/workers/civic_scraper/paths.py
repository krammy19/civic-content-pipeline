"""Single source of truth for every data directory this project writes
to or reads from, resolved from this package's own location - never
from `os.getcwd()`.

This is what fixes the historic "two data/processed/ directories" bug:
every one of these used to be a bare relative `Path("data/processed")`
(or `.cache/llm`, `data/raw`, etc.) defined in whatever module needed
it. A bare relative path resolves against the current working directory
at the moment a command runs, not against the repo - so running the
same command from the repo root versus from `services/workers/`
produced two different absolute paths and silently wrote to two
different trees. Anchoring every path to `__file__`'s own location
means the answer is the same regardless of where a command is invoked
from.
"""

from pathlib import Path

# services/workers/civic_scraper/paths.py -> repo root is three levels up.
REPO_ROOT = Path(__file__).resolve().parents[3]

DATA_ROOT = REPO_ROOT / "data"
DATA_RAW = DATA_ROOT / "raw"
DATA_PROCESSED = DATA_ROOT / "processed"
DATA_REVIEW_QUEUE = DATA_ROOT / "review_queue"
DATA_METRICS = DATA_ROOT / "metrics"
LLM_CACHE = REPO_ROOT / ".cache" / "llm"
