#!/usr/bin/env python3
"""Embed app_data.json into the interactive apps' inline <script id="pw-data"> block.
Run after app_data.py. Updates pw_app.html and risk_app.html in place.

  python embed_app_data.py
"""
import json, sys

DATA = "app_data.json"
APPS = ["pw_app.html", "risk_app.html"]
OPEN = '<script id="pw-data" type="application/json">'
CLOSE = "</script>"

payload = open(DATA).read().strip()
try:
    n = len(json.loads(payload)["products"])
except Exception as e:
    sys.exit(f"app_data.json is not valid JSON: {e}")

for app in APPS:
    html = open(app).read()
    i = html.find(OPEN)
    if i < 0:
        print(f"  [skip] {app}: no pw-data block"); continue
    j = html.find(CLOSE, i + len(OPEN))
    if j < 0:
        print(f"  [skip] {app}: unterminated pw-data block"); continue
    new = html[:i + len(OPEN)] + payload + html[j:]
    open(app, "w").write(new)
    print(f"  embedded {n} products into {app}  ({len(new)/1e6:.2f} MB)")
