src = "fixtures/local_full.json"
dst = "fixtures/local_full_clean.json"

with open(src, "rb") as f:
    raw = f.read()

if raw.startswith(b"\xef\xbb\xbf"):
    raw = raw[3:]

with open(dst, "wb") as f:
    f.write(raw)

print(f"Saved clean JSON without BOM -> {dst}")
