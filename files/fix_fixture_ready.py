import json

SRC = r"fixtures/render_dump.json"
DST = r"fixtures/render_dump_ready.json"

with open(SRC, "r", encoding="utf-8") as f:
    data = json.load(f)

# 1) Ensure we have at least one Gym (pk=1)
has_gym = any(obj.get("model","").lower().endswith("gym") for obj in data)
if not has_gym:
    data.insert(0, {
        "model": "BoxersPresenceApp.gym",
        "pk": 1,
        "fields": {
            "name": "Default Gym",
            "location": ""
        }
    })

# 2) Fix each Boxer:
#   - if "coach" present (string or list), move to "coaches" (list of usernames natural keys)
#   - ensure "gym" is set (default to pk=1 if missing/null)
fixed = 0
coach_fixed = 0
for obj in data:
    if obj.get("model","").lower().endswith("boxer"):
        fields = obj.setdefault("fields", {})

        # normalize coaches
        if "coach" in fields:
            val = fields.pop("coach")
            # val may be "Zefir" or ["Zefir"]; normalize to list[str]
            if val is None:
                fields["coaches"] = []
            elif isinstance(val, list):
                fields["coaches"] = val
            else:
                fields["coaches"] = [val]
            coach_fixed += 1
        else:
            # make sure coaches exists as list (M2M blank OK)
            fields.setdefault("coaches", [])

        # make sure gym is present and not null
        if "gym" not in fields or fields["gym"] in (None, ""):
            fields["gym"] = 1
            fixed += 1

with open(DST, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Fixture ready. Boxers missing gym fixed: {fixed}. Coach field converted on: {coach_fixed}. Wrote {DST}")
