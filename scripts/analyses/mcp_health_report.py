"""State of remote MCP servers, Nov 2026. Reads data/health/raw.jsonl + data/mcp/servers.json,
writes data/reports/mcp-health-2026-11.json. Run from repo root: python3 scripts/analyses/mcp_health_report.py"""
import json, collections as C, statistics as S, os

BULK_MIN = 100  # a namespace (name prefix before '/') with >= this many checked URLs is a "bulk publisher"
raw = [json.loads(l) for l in open("data/health/raw.jsonl")]
reg = {s["name"]: s for s in json.load(open("data/mcp/servers.json"))}
H = json.load(open("data/health/latest.json"))
N = len(raw)

def pct(a, b): return round(100 * a / b, 1) if b else None
def ns(x): return x["name"].split("/")[0]
def alive(x): return x["outcome"] in ("ok", "auth_required")
def stats(xs):
    n = len(xs); ok = sum(x["outcome"] == "ok" for x in xs); au = sum(x["outcome"] == "auth_required" for x in xs)
    return {"n": n, "ok": ok, "ok_pct": pct(ok, n), "auth": au, "auth_pct": pct(au, n), "alive_pct": pct(ok + au, n), "failed_pct": pct(n - ok - au, n)}
def lat(xs):
    v = sorted(x["latency_ms"] for x in xs if x["outcome"] == "ok" and x["latency_ms"] is not None)
    return {"n": len(v), "median": round(S.median(v)) if v else None, "p90": v[int(.9 * (len(v) - 1))] if v else None}

for x in raw:
    r = reg[x["name"]]
    x["month"] = r["first_published"][:7]; x["has_pkg"] = bool(r["packages"]); x["has_repo"] = bool(r["repository"])
    x["cats"] = r["categories"]; x["reg_status"] = r["status"]; x["ns"] = ns(x)

nsc = C.Counter(x["ns"] for x in raw)
bulk = {k for k, v in nsc.items() if v >= BULK_MIN}
for x in raw: x["bulk"] = x["ns"] in bulk
bulk_x = [x for x in raw if x["bulk"]]; other_x = [x for x in raw if not x["bulk"]]

out = {"generated_from": {"checked_date": H["generated"], "urls_checked": N, "registry_entries": len(reg), "bulk_publisher_min_urls": BULK_MIN}}
out["overall"] = stats(raw)
out["overall"]["latency_ok"] = lat(raw)

# concentration
top_ns = nsc.most_common(10)
out["concentration"] = {
  "distinct_namespaces": len(nsc), "distinct_hosts": len({x["host"] for x in raw}),
  "bulk_namespaces": len(bulk), "bulk_urls": len(bulk_x), "bulk_urls_pct": pct(len(bulk_x), N),
  "top5_namespaces": [{"namespace": k, "urls": v, "pct_of_all": pct(v, N), **{kk: vv for kk, vv in stats([x for x in raw if x["ns"] == k]).items() if kk in ("ok_pct", "alive_pct")}} for k, v in top_ns[:5]],
  "top5_namespaces_pct_of_all": pct(sum(v for _, v in top_ns[:5]), N),
  "top10_namespaces": [{"namespace": k, "urls": v, "pct_of_all": pct(v, N), "ok_pct": stats([x for x in raw if x["ns"] == k])["ok_pct"], "alive_pct": stats([x for x in raw if x["ns"] == k])["alive_pct"]} for k, v in top_ns],
  "bulk": stats(bulk_x), "non_bulk": stats(other_x),
  "non_bulk_namespaces": len({x["ns"] for x in other_x}),
}
# per-host (distinct hosts): share of hosts with at least one working server
hostg = C.defaultdict(list)
for x in raw: hostg[x["host"]].append(x)
out["hosts"] = {"distinct": len(hostg),
  "hosts_with_any_ok": sum(any(x["outcome"] == "ok" for x in v) for v in hostg.values()),
  "hosts_with_any_ok_pct": pct(sum(any(x["outcome"] == "ok" for x in v) for v in hostg.values()), len(hostg)),
  "hosts_with_any_alive_pct": pct(sum(any(alive(x) for x in v) for v in hostg.values()), len(hostg)),
  "hosts_single_url": sum(len(v) == 1 for v in hostg.values()),
  "median_urls_per_host": S.median(len(v) for v in hostg.values())}

# age cohorts
def cohort(xs):
    g = C.defaultdict(list)
    for x in xs: g[x["month"]].append(x)
    return [{"month": m, **stats(g[m])} for m in sorted(g)]
def quarter(m): return m[:4] + "-Q" + str((int(m[5:7]) - 1) // 3 + 1)
def qcohort(xs):
    g = C.defaultdict(list)
    for x in xs: g[quarter(x["month"])].append(x)
    return [{"quarter": m, **stats(g[m])} for m in sorted(g)]
out["age"] = {"by_month_all": cohort(raw), "by_quarter_all": qcohort(raw), "by_quarter_non_bulk": qcohort(other_x),
              "by_month_non_bulk": cohort(other_x), "by_quarter_bulk": qcohort(bulk_x)}

# hosting type
def htype(h):
    rules = [("workers.dev", "Cloudflare Workers (*.workers.dev)"), ("pages.dev", "Cloudflare Pages (*.pages.dev)"), ("vercel.app", "Vercel (*.vercel.app)"),
             ("railway.app", "Railway (*.railway.app)"), ("up.railway.app", "Railway (*.railway.app)"), ("fly.dev", "Fly.io (*.fly.dev)"),
             ("smithery.ai", "Smithery (*.smithery.ai)"), ("apify.com", "Apify (*.apify.com)"), ("herokuapp.com", "Heroku (*.herokuapp.com)"),
             ("onrender.com", "Render (*.onrender.com)"), ("netlify.app", "Netlify (*.netlify.app)"), ("run.app", "Google Cloud Run (*.run.app)"),
             ("azurewebsites.net", "Azure (*.azurewebsites.net)"), ("ngrok", "ngrok tunnels"), ("trycloudflare.com", "Cloudflare quick tunnels"),
             ("github.io", "GitHub Pages (*.github.io)"), ("amazonaws.com", "AWS (*.amazonaws.com)"), ("supabase.co", "Supabase (*.supabase.co)"),
             ("deno.dev", "Deno Deploy (*.deno.dev)"), ("modal.run", "Modal (*.modal.run)"), ("koyeb.app", "Koyeb (*.koyeb.app)")]
    for suf, lab in rules:
        if h == suf or h.endswith("." + suf) or (suf == "ngrok" and "ngrok" in h): return lab
    return "Own / other domain"
for x in raw: x["htype"] = htype(x["host"])
def grp(xs, key, minn=1):
    g = C.defaultdict(list)
    for x in xs: g[key(x)].append(x)
    rows = [{"group": k, **stats(v), "latency_ok": lat(v)} for k, v in g.items() if len(v) >= minn]
    return sorted(rows, key=lambda r: -r["n"])
out["hosting"] = {"all": grp(raw, lambda x: x["htype"]), "non_bulk": grp(other_x, lambda x: x["htype"]),
                  "platform_vs_own_all": grp(raw, lambda x: "platform subdomain" if x["htype"] != "Own / other domain" else "own/other domain"),
                  "platform_vs_own_non_bulk": grp(other_x, lambda x: "platform subdomain" if x["htype"] != "Own / other domain" else "own/other domain")}
# latency by host type (ok only), buckets
out["latency_by_hosting_non_bulk"] = [{"group": r["group"], **r["latency_ok"]} for r in out["hosting"]["non_bulk"] if r["latency_ok"]["n"] >= 30]
out["latency_non_bulk"] = lat(other_x); out["latency_bulk"] = lat(bulk_x)

# packages / repo
def pk(x): return ("packages + remote" if x["has_pkg"] else "remote only")
out["packages"] = {"all": grp(raw, pk), "non_bulk": grp(other_x, pk)}
def rp(x): return ("GitHub/other repo listed" if x["has_repo"] else "no repo listed")
out["repository"] = {"all": grp(raw, rp), "non_bulk": grp(other_x, rp)}
out["repository"]["both_nonbulk"] = grp(other_x, lambda x: pk(x) + " / " + rp(x))
out["registry_status"] = {"all": grp(raw, lambda x: x["reg_status"])}

# categories
g = C.defaultdict(list)
for x in raw:
    for c in (x["cats"] or ["(uncategorised)"]): g[c].append(x)
out["categories"] = {"all": sorted([{"category": k, **stats(v)} for k, v in g.items()], key=lambda r: -r["n"])}
g = C.defaultdict(list)
for x in other_x:
    for c in (x["cats"] or ["(uncategorised)"]): g[c].append(x)
out["categories"]["non_bulk"] = sorted([{"category": k, **stats(v)} for k, v in g.items()], key=lambda r: -r["n"])

# protocol
ok = [x for x in raw if x["outcome"] == "ok"]
pv = C.Counter(x["protocol_version"] for x in ok)
out["protocol"] = {"ok_n": len(ok), "counts": dict(pv.most_common()), "pct": {k: pct(v, len(ok)) for k, v in pv.most_common()},
  "requested": "2025-06-18",
  "same_as_requested_pct": pct(pv["2025-06-18"], len(ok)),
  "older_pct": pct(sum(v for k, v in pv.items() if k and k < "2025-06-18"), len(ok)),
  "newer_pct": pct(sum(v for k, v in pv.items() if k and k > "2025-06-18"), len(ok)),
  "non_bulk_counts": dict(C.Counter(x["protocol_version"] for x in other_x if x["outcome"] == "ok").most_common()),
  "non_bulk_ok_n": sum(x["outcome"] == "ok" for x in other_x)}

# tools
tc = [x for x in ok if x["tools_count"] is not None]
def bucket(n): return "0" if n == 0 else "1-5" if n <= 5 else "6-10" if n <= 10 else "11-20" if n <= 20 else "21-50" if n <= 50 else "51-100" if n <= 100 else "101+"
tb = C.Counter(bucket(x["tools_count"]) for x in tc)
order = ["0", "1-5", "6-10", "11-20", "21-50", "51-100", "101+"]
vals = sorted(x["tools_count"] for x in tc)
tot = sum(vals)
top = sorted(tc, key=lambda x: (-x["tools_count"], x["name"]))
out["tools"] = {"n": len(tc), "median": S.median(vals), "mean": round(tot / len(vals), 1), "total_tools": tot,
  "buckets": [{"bucket": b, "n": tb[b], "pct": pct(tb[b], len(tc))} for b in order],
  "top10": [{"name": x["name"], "tools": x["tools_count"], "url": x["url"]} for x in top[:10]],
  "servers_over_50_pct": pct(sum(v > 50 for v in vals), len(vals)),
  "top1pct_share_of_all_tools": pct(sum(vals[-max(1, len(vals) // 100):]), tot),
  "median_non_bulk": S.median(x["tools_count"] for x in tc if not x["bulk"]),
  "n_non_bulk": sum(not x["bulk"] for x in tc),
  "tools_median_with_packages": S.median(x["tools_count"] for x in tc if x["has_pkg"]),
  "tools_median_remote_only": S.median(x["tools_count"] for x in tc if not x["has_pkg"]),
  "exactly_zero_tools": tb["0"]}

# errors
he = [x for x in raw if x["outcome"] == "http_error"]
codes = C.Counter(x["http_status"] for x in he)
out["errors"] = {"http_error_n": len(he), "top_http_status": [{"status": k, "n": v, "pct_of_http_errors": pct(v, len(he)), "pct_of_all": pct(v, N)} for k, v in codes.most_common(8)],
  "outcome_counts": dict(C.Counter(x["outcome"] for x in raw).most_common()),
  "status_404_410_n": codes[404] + codes[410], "status_402_n": codes[402], "status_405_n": codes[405],
  "tunnel_502_errors_n": sum(1 for x in raw if (x["error"] or "").startswith("OSError: Tunnel connection failed")),
  "tunnel_502_errors_pct_of_all": pct(sum(1 for x in raw if (x["error"] or "").startswith("OSError: Tunnel connection failed")), N),
  "tunnel_502_hosts": C.Counter(x["host"] for x in raw if (x["error"] or "").startswith("OSError: Tunnel connection failed")).most_common(3),
  "top_errors": C.Counter(x["error"] for x in raw if x["error"]).most_common(6)}
out["errors"]["outcome_non_tunnel_failed_pct"] = pct(N - sum(x["outcome"] in ("ok", "auth_required") for x in raw) - out["errors"]["tunnel_502_errors_n"], N)
# transport
out["transport"] = grp(raw, lambda x: x["transport"])
# same host ok vs auth: who requires auth
out["auth"] = {"auth_required_n": out["overall"]["auth"], "auth_top_namespaces": C.Counter(x["ns"] for x in raw if x["outcome"] == "auth_required").most_common(5),
  "auth_top_hosts": C.Counter(x["host"] for x in raw if x["outcome"] == "auth_required").most_common(5)}
out["working_top_hosts"] = C.Counter(x["host"] for x in ok).most_common(5)
out["working_top_hosts_pct_of_working"] = pct(sum(v for _, v in out["working_top_hosts"]), len(ok))
out["working_non_bulk"] = {"n": sum(x["outcome"] == "ok" for x in other_x)}

os.makedirs("data/reports", exist_ok=True)
json.dump(out, open("data/reports/mcp-health-2026-11.json", "w"), indent=1, default=list)
print("wrote", len(json.dumps(out)), "bytes")
