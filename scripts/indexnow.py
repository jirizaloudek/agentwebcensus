#!/usr/bin/env python3
"""Notify IndexNow (Bing, Yandex, Seznam, ...) about pages whose content changed since the last run.
State (page -> content hash) is kept in data/indexnow_state.json. Run after build_site.py."""
import hashlib, json, os, sys, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from sitelib import BASE_URL, OUT
KEY = "cbf8489fc08ebfc3949f26793bab4b1c"
STATE = "data/indexnow_state.json"

def main():
    open(os.path.join(OUT, KEY + ".txt"), "w").write(KEY)
    if "--key-only" in sys.argv: return
    old = json.load(open(STATE)) if os.path.exists(STATE) else {}
    new, changed = {}, []
    for root, _, files in os.walk(OUT):
        for f in files:
            if f != "index.html": continue
            p = os.path.join(root, f)
            path = "/" + os.path.relpath(root, OUT).replace(os.sep, "/") + "/"
            path = "/" if path == "/./" else path
            h = hashlib.sha1(open(p, "rb").read()).hexdigest()[:16]
            new[path] = h
            if old.get(path) != h: changed.append(BASE_URL + path)
    if "--dry" in sys.argv:
        print("changed:", len(changed)); return
    host = BASE_URL.split("//", 1)[1].split("/")[0]
    for i in range(0, len(changed), 9000):
        body = json.dumps({"host": host, "key": KEY, "keyLocation": f"{BASE_URL}/{KEY}.txt", "urlList": changed[i:i+9000]}).encode()
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            r = urllib.request.urlopen(req, timeout=60); print("indexnow", r.status, len(changed[i:i+9000]))
        except Exception as e:
            print("indexnow failed:", e); return  # keep old state so we retry next run
    json.dump(new, open(STATE, "w"), separators=(",", ":"), sort_keys=True)

if __name__ == "__main__":
    main()
