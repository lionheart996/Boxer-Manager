import json, sys

src = r"fixtures/render_dump.json"
dst = r"fixtures/render_dump_m2m.json"

with open(src, "r", encoding="utf-8") as f:
    data = json.load(f)

changed = 0
for obj in data:
    if obj.get("model","").endswith("boxer"):
        fields = obj.get("fields", {})
        if "coach" in fields:
            coach = fields.pop("coach")
            if coach is not None:
                # current schema expects a list of user PKs
                fields["coaches"] = [coach]
                changed += 1

with open(dst, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Converted {changed} boxer records. Wrote {dst}")
