#!/usr/bin/env python3
"""Compute MCP Registry statistics from data/raw/registry.jsonl -> data/mcp/latest.json (+ history row)."""
import json, sys, os, re, statistics, collections, datetime as dt
RAW = sys.argv[1] if len(sys.argv) > 1 else "data/raw/registry.jsonl"
OUT = "data/mcp"
os.makedirs(OUT, exist_ok=True)
C = collections.Counter

CATS = {  # keyword -> category, applied to name+title+description (lowercase). Transparent & simple.
 "database": r"\b(sql|postgres|mysql|sqlite|mongo|database|db|redis|supabase|bigquery|snowflake|clickhouse|duckdb)\b",
 "dev tools & code": r"\b(github|gitlab|git|code|repo|ci/cd|devops|kubernetes|docker|terraform|lint|debug|ide)\b",
 "search & web": r"\b(search|web ?scrap|crawl|browser|scrape|serp|fetch|website)\b",
 "finance & crypto": r"\b(finance|stock|trading|crypto|bitcoin|ethereum|blockchain|defi|payment|invoice|bank|wallet|solana)\b",
 "ai & media generation": r"\b(image|video|audio|speech|tts|llm|embedding|generat|vision|ocr|transcri)\w*",
 "productivity & docs": r"\b(notion|calendar|email|gmail|slack|docs|spreadsheet|sheets|todo|task|jira|confluence|drive|office)\b",
 "marketing & seo": r"\b(seo|marketing|ads|analytics|crm|hubspot|salesforce|social media|twitter|linkedin)\b",
 "commerce": r"\b(shop|e-?commerce|store|product|order|shopify|amazon|retail)\b",
 "security": r"\b(security|vulnerab|pentest|threat|malware|cve|auth|secret)\w*",
 "maps & travel": r"\b(map|geo|travel|flight|hotel|weather|location)\w*",
 "memory & knowledge": r"\b(memory|knowledge|rag|vector|notes|wiki)\b",
 "cloud & infra": r"\b(aws|azure|gcp|cloudflare|vercel|server ?less|infra|monitoring|observability|logs?)\b",
}
CATS = {k: re.compile(v) for k, v in CATS.items()}

def ts(s): return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))

recs = []
for line in open(RAW):
    try: recs.append(json.loads(line))
    except Exception: pass

by_name = collections.defaultdict(list)
for r in recs:
    by_name[r["server"]["name"]].append(r)

def meta(r): return r["_meta"]["io.modelcontextprotocol.registry/official"]

latest = {}
first_pub = {}
for name, rs in by_name.items():
    rs.sort(key=lambda r: meta(r)["publishedAt"])
    first_pub[name] = ts(meta(rs[0])["publishedAt"])
    latest[name] = rs[-1]  # newest publishedAt (robust with incremental fetches; isLatest flags may be stale)

now = dt.datetime.now(dt.timezone.utc)
L = list(latest.values())
S = [r["server"] for r in L]
n = len(S)
pct = lambda a, b=None: round(100.0 * a / (b if b is not None else n), 1) if (b if b is not None else n) else 0.0

status = C(meta(r)["status"] for r in L)
remote_types, pkg_types, transports, remote_hosts = C(), C(), C(), set()
has_remote = has_pkg = both = has_repo = gh_repo = has_icon = has_web = has_title = 0
env_req = 0
for s in S:
    rem = s.get("remotes") or []; pk = s.get("packages") or []
    if rem: has_remote += 1
    if pk: has_pkg += 1
    if rem and pk: both += 1
    for t in {x.get("type") for x in rem}: remote_types[t] += 1
    for x in rem:
        m = re.match(r"https?://([^/:]+)", x.get("url", ""))
        if m: remote_hosts.add(m.group(1).lower())
    for t in {p.get("registryType") for p in pk}: pkg_types[t] += 1
    for t in {(p.get("transport") or {}).get("type") for p in pk}: transports[t] += 1
    if any(p.get("environmentVariables") for p in pk): env_req += 1
    repo = (s.get("repository") or {}).get("url") or ""
    if repo: has_repo += 1
    if "github.com" in repo: gh_repo += 1
    if s.get("icons"): has_icon += 1
    if s.get("websiteUrl"): has_web += 1
    if s.get("title"): has_title += 1

ns = C(s["name"].split("/")[0] for s in S)
ns_kind = C("io.github.*" if k.startswith("io.github.") else ("com.*" if k.startswith("com.") else ("io.*" if k.startswith("io.") else ("ai.*" if k.startswith("ai.") else "other"))) for k in (s["name"].split("/")[0] for s in S))

cats = C()
uncat = 0
for s in S:
    txt = " ".join([s.get("name", "").split("/", 1)[-1], s.get("title", "") or "", s.get("description", "") or ""]).lower()
    hit = [k for k, rx in CATS.items() if rx.search(txt)]
    for k in hit: cats[k] += 1
    if not hit: uncat += 1

vers = [len(v) for v in by_name.values()]
desc_len = [len(s.get("description") or "") for s in S]

# growth from first publication date (registry history reconstructed from publishedAt)
monthly = C(d.strftime("%Y-%m") for d in first_pub.values())
daily = C(d.strftime("%Y-%m-%d") for d in first_pub.values())
cum, run = [], 0
for m in sorted(monthly):
    run += monthly[m]; cum.append({"month": m, "new": monthly[m], "cumulative": run})
def new_since(days): return sum(1 for d in first_pub.values() if (now - d).days < days)
since7 = (now.date() - dt.timedelta(days=6)).isoformat()  # rolling 7 UTC calendar days incl. today
new_7d = sum(1 for d in first_pub.values() if d.date().isoformat() >= since7)
ver_last = lambda days: sum(1 for r in recs if (now - ts(meta(r)["publishedAt"])).days < days)
updated_30 = sum(1 for r in L if (now - ts(meta(r)["updatedAt"])).days < 30)

last_full = sorted(m for m in monthly if m < now.strftime("%Y-%m"))
mom = None
if len(last_full) >= 2:
    a, b = monthly[last_full[-2]], monthly[last_full[-1]]
    mom = round(100.0 * (b - a) / a, 1) if a else None

first_seen = min(first_pub.values())
stats = {
  "generated_at": now.isoformat(timespec="seconds"),
  "source": "https://registry.modelcontextprotocol.io/v0/servers (official MCP Registry, full crawl)",
  "license": "CC BY 4.0 — cite as: MCP Census (mcpcensus), data from the official MCP Registry",
  "totals": {
    "servers": n, "version_records": len(recs), "active": status.get("active", 0),
    "deprecated": status.get("deprecated", 0), "namespaces": len(ns),
    "avg_versions_per_server": round(statistics.mean(vers), 2), "median_versions_per_server": statistics.median(vers),
    "first_server_published": first_seen.date().isoformat(),
  },
  "growth": {
    "new_servers_last_24h": new_since(1), "new_servers_last_7d": new_7d, "new_7d_first_published_on_or_after": since7, "new_servers_last_30d": new_since(30),
    "version_publishes_last_7d": ver_last(7), "version_publishes_last_30d": ver_last(30),
    "servers_updated_last_30d": updated_30, "last_full_month_mom_growth_pct": mom,
    "monthly": cum,
    "daily_last_60": [{"date": d, "new": daily[d]} for d in sorted(daily)[-60:]],
  },
  "deployment": {
    "remote_servers": has_remote, "remote_pct": pct(has_remote), "package_servers": has_pkg, "package_pct": pct(has_pkg),
    "remote_and_package": both, "remote_transport": dict(remote_types.most_common()),
    "package_registry": dict(pkg_types.most_common()), "package_transport": dict(transports.most_common()),
    "unique_remote_hosts": len(remote_hosts), "packages_requiring_env_vars": env_req,
    "packages_requiring_env_vars_pct": pct(env_req, has_pkg),
  },
  "metadata_quality": {
    "with_repository_pct": pct(has_repo), "github_hosted_repo_pct": pct(gh_repo), "with_icon_pct": pct(has_icon),
    "with_website_pct": pct(has_web), "with_title_pct": pct(has_title),
    "median_description_chars": statistics.median(desc_len),
  },
  "concentration": {"top10_publishers_share_pct": pct(sum(v for _, v in ns.most_common(10))),
                    "top100_publishers_share_pct": pct(sum(v for _, v in ns.most_common(100))),
                    "publishers_with_one_server": sum(1 for v in ns.values() if v == 1),
                    "publishers_with_100plus": sum(1 for v in ns.values() if v >= 100)},
  "namespaces": {"by_kind": dict(ns_kind.most_common()), "top_25": [{"namespace": k, "servers": v} for k, v in ns.most_common(25)]},
  "categories": {"method": "keyword match on name/title/description; a server may be in several categories",
                 "counts": dict(cats.most_common()), "uncategorized": uncat},
}
# compact per-server list (latest version) for directory pages + API
rows = []
for name, r in latest.items():
    s = r["server"]; m = meta(r)
    txt = " ".join([s.get("name", "").split("/", 1)[-1], s.get("title", "") or "", s.get("description", "") or ""]).lower()
    rows.append({"name": name, "title": s.get("title") or "", "description": (s.get("description") or "")[:200],
        "status": m.get("status"),
        "categories": [k for k, rx in CATS.items() if rx.search(txt)],
        "remotes": sorted({x.get("type") for x in (s.get("remotes") or []) if x.get("type")}),
        "remote_urls": [x.get("url") for x in (s.get("remotes") or [])][:2],
        "packages": sorted({p.get("registryType") for p in (s.get("packages") or []) if p.get("registryType")}),
        "package_ids": [f'{p.get("registryType")}:{p.get("identifier")}' for p in (s.get("packages") or [])][:3],
        "repository": (s.get("repository") or {}).get("url") or "",
        "first_published": first_pub[name].date().isoformat(), "updated": m.get("updatedAt", "")[:10],
        "versions": len(by_name[name])})
rows.sort(key=lambda x: x["updated"], reverse=True)
json.dump(rows, open(f"{OUT}/servers.json", "w"), separators=(",", ":"))
json.dump(stats, open(f"{OUT}/latest.json", "w"), indent=1)
hist = f"{OUT}/history.csv"
row = [now.date().isoformat(), n, len(recs), status.get("active", 0), has_remote, has_pkg, len(ns), new_7d]
new = not os.path.exists(hist)
lines = open(hist).read().splitlines() if not new else ["date,servers,version_records,active,remote,package,namespaces,new_7d"]
lines = [l for l in lines if not l.startswith(row[0])] + [",".join(map(str, row))]
open(hist, "w").write("\n".join(lines) + "\n")
print(json.dumps(stats["totals"]), json.dumps(new_7d))
