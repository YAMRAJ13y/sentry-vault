"""Crops the Yamlok logo emblem and produces web-ready assets + base64 tokens."""
from PIL import Image
import base64
import os

SRC = "S:/Projects/Claude Code/Yamlok/yamraj logo.png"
G = "S:/Projects/Z code/cloud project sem 3/sentry-vault-github"
os.makedirs(G + "/assets", exist_ok=True)

img = Image.open(SRC).convert("RGB")
w, h = img.size
print("source:", w, "x", h)

# square center crop around the emblem
side = min(w, h)
cx, cy = w // 2, int(h * 0.44)
left = max(0, cx - side // 2)
top = max(0, cy - side // 2)
sq = img.crop((left, top, min(w, left + side), min(h, top + side)))

# big version for README (640px)
big = sq.resize((640, 640), Image.LANCZOS)
big.save(G + "/assets/logo.png", optimize=True)

# header avatar (140px) + favicon (64px)
small = sq.resize((140, 140), Image.LANCZOS)
small.save(G + "/assets/logo-header.png", optimize=True)
fav = sq.resize((64, 64), Image.LANCZOS)
fav.save(G + "/assets/favicon.png", optimize=True)

for f, n in (("assets/logo-header.png", "header"), ("assets/favicon.png", "favicon")):
    b = base64.b64encode(open(G + "/" + f, "rb").read()).decode()
    out = f"S:/Projects/Z code/cloud project sem 3/sentry-vault/b64_{n}.txt"
    open(out, "w").write(b)
    print(n, "b64 len:", len(b))

print("assets done")
