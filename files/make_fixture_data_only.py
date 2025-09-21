# make_fixture_data_only.py
import json

src = "fixtures/local_full_strict.json"
dst = "fixtures/local_data_only.json"

with open(src, "r", encoding="utf-8") as f:
    data = json.load(f)

filtered = []
skipped = 0
for obj in data:
    model = obj.get("model", "")
    if model.startswith("auth.") or model.startswith("contenttypes.") or model.startswith("sessions."):
        skipped += 1
        continue
    if model == "BoxersPresenceApp.coachprofile":
        skipped += 1
        continue
    filtered.append(obj)

with open(dst, "w", encoding="utf-8") as f:
    json.dump(filtered, f, ensure_ascii=False, indent=2)

print(f"Written {dst} with {len(filtered)} objects (skipped {skipped})")
