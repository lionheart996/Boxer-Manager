import json

src = "fixtures/local_data_only.json"   # the file you just built
dst = "fixtures/local_data_no_admin.json"

with open(src, "r", encoding="utf-8") as f:
    data = json.load(f)

filtered = []
skipped = 0
for obj in data:
    model = (obj.get("model") or "")
    if model.startswith(("admin.",)):          # remove admin.LogEntry, etc
        skipped += 1
        continue
    filtered.append(obj)

with open(dst, "w", encoding="utf-8") as f:
    json.dump(filtered, f, ensure_ascii=False, indent=2)

print(f"Wrote {dst} with {len(filtered)} objects (skipped {skipped})")
