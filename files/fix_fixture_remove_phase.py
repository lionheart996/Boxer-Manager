import json

SRC = r"fixtures/render_dump_FINAL.json"
DST = r"fixtures/render_dump_FINAL_clean.json"

with open(SRC, "r", encoding="utf-8") as f:
    data = json.load(f)

removed = 0
for obj in data:
    model = (obj.get("model") or "").lower()
    if model.endswith("weight") or model.endswith(".weight"):
        fields = obj.get("fields", {})
        if "phase" in fields:
            fields.pop("phase", None)
            removed += 1

with open(DST, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Removed 'phase' from {removed} Weight objects. Wrote {DST}")
