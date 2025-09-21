import json

src = "fixtures/local_data_no_admin.json"
dst = "fixtures/local_data_no_admin_nocoaches.json"

with open(src, "r", encoding="utf-8") as f:
    data = json.load(f)

changed = 0
for obj in data:
    model = (obj.get("model") or "").lower()
    if model.endswith("boxerspresenceapp.boxer"):
        fields = obj.setdefault("fields", {})
        if "coaches" in fields and fields["coaches"]:
            fields["coaches"] = []   # clear M2M to auth.User
            changed += 1
    if model.endswith("boxerspresenceapp.classtemplate"):
        fields = obj.setdefault("fields", {})
        if "coaches" in fields and fields["coaches"]:
            fields["coaches"] = []   # clear M2M on class templates too
            changed += 1

print(f"Cleared coaches on {changed} objects")
with open(dst, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"Wrote {dst}")
