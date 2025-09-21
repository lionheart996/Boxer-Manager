import json

src = "fixtures/local_full.json"
dst = "fixtures/local_full_strict.json"

# Open with errors="replace" so invalid bytes get fixed
with open(src, "r", encoding="utf-8", errors="replace") as f:
    data = json.load(f)

with open(dst, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Re-saved JSON in strict UTF-8 -> {dst}")
