"""Validate a text result in the restricted execution container."""
import sys
from pathlib import Path
p = Path(sys.argv[1])
text = p.read_text(encoding="utf-8")
if not text.strip() or "\x00" in text:
    raise SystemExit("invalid text artifact")
print(f"validated {len(text)} characters")
