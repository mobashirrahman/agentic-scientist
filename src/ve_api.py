"""Minimal client for the Virtual Embryo Challenge API (https://api.virtualembryo.ai/docs)."""
import json, os, pathlib, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]

def _env():
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())
_env()
BASE = os.environ.get("VE_API_BASE", "https://api.virtualembryo.ai")
KEY = os.environ.get("VE_API_KEY")

def get(path, auth=True, **params):
    url = f"{BASE}{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {KEY}"} if auth else {})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())
