import json

SRC = r"fixtures/render_dump.json"
DST = r"fixtures/render_dump_ready_ids.json"

with open(SRC, "r", encoding="utf-8") as f:
    data = json.load(f)

# Map usernames -> integer PKs from auth.user objects in the fixture
username_to_pk = {}
for obj in data:
    if obj.get("model") in ("auth.user", "auth.User", "auth.user"):
        pk = obj.get("pk")
        username = obj.get("fields", {}).get("username")
        if username:
            username_to_pk[username] = pk

# Ensure at least one Gym (pk=1)
has_gym = any(obj.get("model","").lower().endswith("gym") for obj in data)
if not has_gym:
    data.insert(0, {
        "model": "BoxersPresenceApp.gym",
        "pk": 1,
        "fields": {"name": "Default Gym", "location": ""}
    })

fixed_gym = 0
fixed_coaches = 0
converted_single_coach = 0

for obj in data:
    model = obj.get("model","").lower()
    if model.endswith("boxer"):
        fields = obj.setdefault("fields", {})

        # Convert legacy single 'coach' -> 'coaches'
        if "coach" in fields:
            val = fields.pop("coach")
            # normalize to list of usernames
            if val is None:
                usernames = []
            elif isinstance(val, list):
                usernames = val
            else:
                usernames = [val]
            # map to integer PKs (drop unknown usernames gracefully)
            pks = [username_to_pk[u] for u in usernames if u in username_to_pk]
            fields["coaches"] = pks
            converted_single_coach += 1
        else:
            # If coaches already present as usernames, map them
            if isinstance(fields.get("coaches"), list) and fields["coaches"] and isinstance(fields["coaches"][0], str):
                fields["coaches"] = [username_to_pk[u] for u in fields["coaches"] if u in username_to_pk]
                fixed_coaches += 1
            else:
                fields.setdefault("coaches", [])

        # Ensure non-null gym (default to pk=1)
        if "gym" not in fields or fields["gym"] in (None, ""):
            fields["gym"] = 1
            fixed_gym += 1

with open(DST, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Users mapped: {len(username_to_pk)} | Boxers fixed gym: {fixed_gym} | "
      f"Converted legacy 'coach': {converted_single_coach} | Mapped 'coaches' usernames: {fixed_coaches} | Wrote {DST}")
