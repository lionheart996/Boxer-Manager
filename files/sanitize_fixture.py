import os, json, django
from pathlib import Path

# point Django at your settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "boxers_project.settings")
# DB URL already set in your session; not strictly needed to introspect, but fine if present.
django.setup()

from django.apps import apps
from django.db.models.fields.related import ManyToManyField

SRC = r"fixtures/render_dump_FINAL.json"   # latest file you had after earlier fixes
DST = r"fixtures/render_dump_SANITIZED.json"

# Build a map of "app_label.modelname" -> allowed field names
allowed = {}
for Model in apps.get_models():
    label = f"{Model._meta.app_label}.{Model._meta.model_name}".lower()
    fields = set(f.name for f in Model._meta.get_fields() if not (getattr(f, 'auto_created', False) and not getattr(f, 'concrete', False)))
    allowed[label] = fields

def sanitize_object(obj):
    model_label = (obj.get("model") or "").lower()
    fields = obj.get("fields", {})
    if not isinstance(fields, dict):
        return obj

    if model_label in allowed:
        keep = allowed[model_label]
        # drop unknown keys
        for k in list(fields.keys()):
            if k not in keep:
                fields.pop(k, None)

        # special handling for BoxersPresenceApp.boxer
        if model_label.endswith("boxerspresenceapp.boxer"):
            # ensure gym FK not null
            if "gym" not in fields or fields["gym"] in (None, ""):
                fields["gym"] = 1
            # to avoid M2M NULLs: clear coaches (you can reassign later)
            if "coaches" in fields and not isinstance(fields["coaches"], list):
                fields["coaches"] = []
            else:
                fields["coaches"] = []

    obj["fields"] = fields
    return obj

# ensure there is at least one Gym (pk=1)
def ensure_default_gym(objs):
    has_gym = any((o.get("model","").lower().endswith("boxerspresenceapp.gym")) for o in objs)
    if not has_gym:
        objs.insert(0, {
            "model": "BoxersPresenceApp.gym",
            "pk": 1,
            "fields": {"name": "Default Gym", "location": ""}
        })

with open(SRC, "r", encoding="utf-8") as f:
    data = json.load(f)

ensure_default_gym(data)
data = [sanitize_object(o) for o in data]

with open(DST, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Sanitized fixture written to {DST}")
