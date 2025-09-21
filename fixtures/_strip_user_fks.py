import json

src = "fixtures/local_data_no_admin_nocoaches.json"
dst = "fixtures/local_data_no_admin_nocoaches_nousers.json"

with open(src, "r", encoding="utf-8") as f:
    data = json.load(f)

changed = 0
for obj in data:
    fields = obj.get("fields", {})
    for fk in ("user", "created_by", "updated_by", "coach", "owner"):  # common FK names
        if fk in fields and isinstance(fields[fk], list):
            fields[fk] = None
            changed += 1

print(f"Cleared {changed} user FKs")
with open(dst, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"Wrote {dst}")
