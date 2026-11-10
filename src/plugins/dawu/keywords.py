import json
from pathlib import Path

_keywords_path = Path(__file__).parent.parent.parent / "asserts" / "dawu" / "keywords.json"
KEYWORDS = json.loads(_keywords_path.read_text(encoding="utf-8"))
