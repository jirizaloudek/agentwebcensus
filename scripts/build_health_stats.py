#!/usr/bin/env python3
"""data/health/raw.jsonl + data/mcp/servers.json -> data/health/{latest.json,servers.json,history.csv}"""
import json, os, csv, statistics, collections, datetime as dt

OUTCOMES = ["ok", "auth_required", "http_error", "timeout", "dns_error", "tls_error", "conn_error", "invalid_response"]
BUCKETS = [("0", 0, 0), ("1-5", 1, 5), ("6-10", 6, 10), ("11-20", 11, 20), ("21-50", 21, 50), ("51+", 51, 10**9)]
pct = lambda a, b: round(100 * a / b, 1) if b else 0.0
def p90(v): v = sorted(v); return v[min(len(v) - 1, int(0.9 * len(v)))] if v else None

def main():
    R = {}
    for l in open("data/health/raw.jsonl"):
        try: r = json.loads(l); R[r["url"]] = r
        except Exception: pass
    R = list(R.values()); N = len(R)
    cats = {s["name"]: s.get("categories") or ["uncategorized"] for s in json.load(open("data/mcp/servers.json"))}
    day = max((r["checked"] for r in R), default=dt.date.today().isoformat())
    oc = collections.Counter(r["outcome"] for r in R)
    ok = [r for r in R if r["outcome"] == "ok"]
    lat = [r["latency_ms"] for r in ok if r.get("latency_ms") is not None]
    tools = [r["tools_count"] for r in ok if r.get("tools_count") is not None]
    hosts = collections.defaultdict(list)
    for r in R: hosts[r["host"]].append(r)
    top = sorted(hosts.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:20]
    bycat = collections.defaultdict(collections.Counter)
    for r in R:
        for c in cats.get(r["name"], ["uncategorized"]): bycat[c][r["outcome"]] += 1; bycat[c]["_n"] += 1
    H = {
      "generated": day, "checked": N, "legacy_sse_checked": sum(1 for r in R if r["transport"] == "sse"),
      "totals": {o: {"n": oc.get(o, 0), "pct_of_checked": pct(oc.get(o, 0), N)} for o in OUTCOMES},
      "alive_pct_of_checked": pct(oc["ok"] + oc["auth_required"], N),
      "latency_ms_ok": {"median": int(statistics.median(lat)) if lat else None, "p90": p90(lat), "n": len(lat)},
      "protocol_versions": dict(collections.Counter(r["protocol_version"] for r in ok if r.get("protocol_version")).most_common()),
      "tools": {"n_with_count": len(tools), "median": statistics.median(tools) if tools else None, "mean": round(statistics.mean(tools), 1) if tools else None,
                "buckets": {b: sum(1 for t in tools if lo <= t <= hi) for b, lo, hi in BUCKETS}},
      "top_hosts": [{"host": h, "servers": len(v), "ok_pct": pct(sum(1 for r in v if r["outcome"] == "ok"), len(v))} for h, v in top],
      "by_category": {c: {"n": v["_n"], **{o: v.get(o, 0) for o in OUTCOMES}, "ok_pct": pct(v.get("ok", 0), v["_n"])} for c, v in sorted(bycat.items(), key=lambda kv: -kv[1]["_n"])},
      "methodology": ("For each server in the official MCP Registry that lists at least one remote URL, we test the first remote URL only (identical URLs are checked once) with a single attempt per week: "
        "one MCP initialize JSON-RPC POST (protocol 2025-06-18; JSON and SSE responses accepted), 10 s timeout, 256 KB body cap. If it succeeds without authentication we send notifications/initialized and one tools/list to count tools (first page only); no tool is ever called. "
        "Legacy SSE-type remotes get a GET and are classed reachable if an event stream starts within 5 s (no tool count). Caveats: a single attempt means transient failures (timeouts, 5xx, rate limits) can be counted as broken; "
        "auth_required (HTTP 401/403 or a WWW-Authenticate header) means the endpoint is alive but needs credentials, so we cannot tell whether it works for authorised users; "
        "servers listing several remotes are judged by the first only; registry entries can be stale. Checked from a single network location."),
    }
    os.makedirs("data/health", exist_ok=True)
    json.dump(H, open("data/health/latest.json", "w"), indent=1)
    json.dump([{k: r.get(k) for k in ("name", "url", "outcome", "http_status", "latency_ms", "tools_count", "protocol_version", "checked")} for r in sorted(R, key=lambda r: r["name"])],
              open("data/health/servers.json", "w"), separators=(",", ":"))
    row = {"date": day, "checked": N, **{o: oc.get(o, 0) for o in OUTCOMES}, "median_latency_ms": H["latency_ms_ok"]["median"], "median_tools": H["tools"]["median"]}
    rows = []
    if os.path.exists("data/health/history.csv"): rows = [r for r in csv.DictReader(open("data/health/history.csv")) if r["date"] != day]
    rows.append({k: str(v) if v is not None else "" for k, v in row.items()})
    with open("data/health/history.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row)); w.writeheader(); w.writerows(rows)
    print(json.dumps({"checked": N, "totals": {o: oc.get(o, 0) for o in OUTCOMES}, "latency": H["latency_ms_ok"], "tools_median": H["tools"]["median"]}))

if __name__ == "__main__": main()
