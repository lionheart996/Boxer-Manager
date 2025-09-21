import json
from pathlib import Path

fixtures_dir = Path("fixtures")
clean_dir = fixtures_dir / "clean"
clean_dir.mkdir(exist_ok=True)

for f in fixtures_dir.glob("render_*.json"):
    try:
        # Read with fallback decoding
        raw = f.read_text(encoding="utf-8-sig", errors="replace")
        data = json.loads(raw)
    except Exception as e:
        print(f"❌ Failed to load {f.name}: {e}")
        continue

    # Write clean UTF-8
    out_file = clean_dir / f.name
    out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ Cleaned {f.name} -> {out_file}")
