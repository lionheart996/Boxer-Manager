import json

SRC = r"fixtures/render_dump_ready_ids.json"  # use the last file you generated
DST = r"fixtures/render_dump_FINAL.json"

with open(SRC, "r", encoding="utf-8") as f:
    data = json.load(f)

for obj in data:
    if obj.get("model","").lower().endswith("boxer"):
        fields = obj.setdefault("fields", {})
        # force coaches to empty list to avoid null user_id in through table
        fields["coaches"] = []
        # ensure gym is set (keep your earlier default of 1 if missing)
        if "gym" not in fields or fields["gym"] in (None, ""):
            fields["gym"] = 1

with open(DST, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Wrote {DST} with coaches cleared and gyms ensured.")
