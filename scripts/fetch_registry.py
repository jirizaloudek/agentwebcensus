#!/usr/bin/env python3
"""Download the full official MCP Registry (all server versions) to data/raw/registry.jsonl."""
import json, os, sys, time, urllib.request, urllib.parse
BASE = "https://registry.modelcontextprotocol.io/v0/servers"
out = sys.argv[1] if len(sys.argv) > 1 else "data/raw/registry.jsonl"
os.makedirs(os.path.dirname(out), exist_ok=True)
# Incremental mode: if a previous full crawl exists (Actions cache), fetch only records updated since then
# and merge by (name, version). Set FULL=1 to force a full crawl (done weekly to catch removals).
prev = {}
since = None
if os.path.exists(out) and os.environ.get("FULL") != "1":
    for line in open(out):
        try: r = json.loads(line)
        except Exception: continue
        prev[(r["server"]["name"], r["server"]["version"])] = line.rstrip("\n")
        u = r["_meta"]["io.modelcontextprotocol.registry/official"]["updatedAt"]
        since = u if since is None or u > since else since
    if since:  # 2 h safety overlap
        import datetime as _dt
        since = (_dt.datetime.fromisoformat(since.replace("Z", "+00:00")) - _dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        print("incremental since", since, "prev records", len(prev))
cursor, n, pages = None, 0, 0
with open(out + ".tmp", "w") as f:
    while True:
        q = {"limit": "100"}
        if since: q["updated_since"] = since
        if cursor: q["cursor"] = cursor
        url = BASE + "?" + urllib.parse.urlencode(q)
        for attempt in range(5):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "AgentWebCensusBot/0.1 (+https://jirizaloudek.github.io/agentwebcensus/about/)"})
                d = json.load(urllib.request.urlopen(req, timeout=60)); break
            except Exception as e:
                print("retry", attempt, e, file=sys.stderr); time.sleep(2 ** attempt)
        else:
            sys.exit("failed: " + url)
        for s in d.get("servers", []):
            line = json.dumps(s, separators=(",", ":"))
            if since: prev[(s["server"]["name"], s["server"]["version"])] = line
            else: f.write(line + "\n")
            n += 1
        pages += 1
        cursor = (d.get("metadata") or {}).get("nextCursor")
        if not cursor or not d.get("servers"): break
    if since:
        for line in prev.values(): f.write(line + "\n")
os.replace(out + ".tmp", out)
print(f"records={n} pages={pages}")
