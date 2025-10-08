from pathlib import Path
import sys


# Ensure 'src' is importable for tests that import 'extractor.*'
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

