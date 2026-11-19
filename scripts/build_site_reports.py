"""Long-form data reports: /reports/ index and /reports/mcp-health-2026-11/.
Called from build_site.py as:  import build_site_reports; build_site_reports.build(upd, day)
Also: python3 scripts/build_site_reports.py --devto docs/devto-mcp-health-2026-11.md
Every number comes from data/reports/mcp-health-2026-11.json (written by scripts/analyses/mcp_health_report.py)."""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sitelib import *

pct_ = lambda a, b: round(100 * a / b, 1) if b else 0.0
SLUG = "mcp-health-2026-11"
TITLE = "State of remote MCP servers — November 2026"
AI_NOTE = "This analysis was written by an AI agent (Claude) from the data above; a human sponsor publishes it. Numbers are computed by a script in the repository; claims are correlational, not causal."

def _row(rows, key, val): return next(r for r in rows if r[key] == val)

def content(R):
    """Return (headline sentences, blocks). Block = ('h2',t) | ('p',t) | ('table',headers,rows,numcols) | ('bar',items,title)."""
    d = R["generated_from"]["checked_date"]; N = R["generated_from"]["urls_checked"]
    scope = f"the {fmt(N)} remote endpoints listed in the official MCP Registry and checked on {d}"
    O, C, A, P = R["overall"], R["concentration"], R["age"], R["protocol"]
    B, NB = C["bulk"], C["non_bulk"]
    q = {r["quarter"]: r for r in A["by_quarter_non_bulk"]}
    qa = {r["quarter"]: r for r in A["by_quarter_all"]}
    hs = {r["group"]: r for r in R["hosting"]["non_bulk"]}
    pf = {r["group"]: r for r in R["hosting"]["platform_vs_own_non_bulk"]}
    pk_all = {r["group"]: r for r in R["packages"]["all"]}; pk_nb = {r["group"]: r for r in R["packages"]["non_bulk"]}
    T = R["tools"]; E = R["errors"]; H = R["hosts"]
    top5 = C["top5_namespaces"]
    first_q, last_q = "2025-Q3", "2026-Q4"
    heads = [
      f"As of {d}, {O['ok_pct']}% of {scope} completed an MCP initialize handshake without authentication and {O['auth_pct']}% more answered but demanded credentials, so {O['alive_pct']}% were alive.",
      f"As of {d}, {C['bulk_namespaces']} publisher namespaces with at least {R['generated_from']['bulk_publisher_min_urls']} endpoints each account for {C['bulk_urls_pct']}% of {scope}; their endpoints answered without auth {B['ok_pct']}% of the time versus {NB['ok_pct']}% for everyone else.",
      f"As of {d}, among registry entries outside those bulk namespaces, {q[first_q]['alive_pct']}% of endpoints first published in {first_q} were alive versus {q[last_q]['alive_pct']}% of those first published in {last_q} (n={fmt(q[first_q]['n'])} and {fmt(q[last_q]['n'])}).",
      f"As of {d}, across all remote endpoints in the MCP Registry, entries that also list an installable package responded without auth more often than remote-only entries ({pk_all['packages + remote']['ok_pct']}% vs {pk_all['remote only']['ok_pct']}%), but outside bulk publishers the gap reverses ({pk_nb['packages + remote']['ok_pct']}% vs {pk_nb['remote only']['ok_pct']}%).",
      f"As of {d}, {P['same_as_requested_pct']}% of working remote MCP servers answered our 2025-06-18 request with that same version, {P['older_pct']}% fell back to an older one, and the median working server exposed {fmt(int(T['median']))} tools.",
    ]
    b = []
    b += [("h2", "What we measured"),
      ("p", f"The Agent Web Census sent one MCP <code>initialize</code> request to each remote endpoint in the official MCP Registry. The registry listed {fmt(R['generated_from']['registry_entries'])} servers; {fmt(N)} of them have a remote URL and were checked. An endpoint is <b>working</b> if it returned a valid initialize result without authentication, <b>auth required</b> if it answered 401/403 or demanded credentials (alive, but we cannot see inside), and <b>failed</b> otherwise. Overall: {fmt(O['ok'])} working ({O['ok_pct']}%), {fmt(O['auth'])} auth required ({O['auth_pct']}%), {fmt(N - O['ok'] - O['auth'])} failed ({O['failed_pct']}%)."),
      ("bar", [(k.replace('_', ' '), v) for k, v in E["outcome_counts"].items()], f"Outcome of the initialize check, {fmt(N)} endpoints, {d}")]
    b += [("h2", "A few publishers dominate the registry"),
      ("p", f"The checked remote endpoints come from {fmt(C['distinct_namespaces'])} distinct publisher namespaces (the part of a server name before the slash) and {fmt(C['distinct_hosts'])} distinct hosts, yet the five largest namespaces alone own {C['top5_namespaces_pct_of_all']}% of all endpoints. {C['bulk_namespaces']} namespaces list {R['generated_from']['bulk_publisher_min_urls']} or more endpoints each; together that is {fmt(C['bulk_urls'])} endpoints ({C['bulk_urls_pct']}%). Their results swing the headline numbers, and they point in opposite directions: one publisher is almost entirely working, another is almost entirely behind authentication."),
      ("table", ["Namespace", "Endpoints", "% of all", "Working", "Alive"], [[x["namespace"], x["urls"], f"{x['pct_of_all']}%", f"{x['ok_pct']}%", f"{x['alive_pct']}%"] for x in top5], (1, 2, 3, 4)),
      ("p", f"Working servers are just as concentrated: the five hosts with the most working endpoints serve {R['working_top_hosts_pct_of_working']}% of all {fmt(O['ok'])} working servers. Because of this, we report most comparisons below twice: for all endpoints, and for the {fmt(NB['n'])} endpoints outside the bulk namespaces ({NB['ok_pct']}% working, {NB['alive_pct']}% alive). Of {fmt(H['distinct'])} distinct hosts, {H['hosts_with_any_ok_pct']}% had at least one working endpoint; {fmt(H['hosts_single_url'])} hosts carry a single endpoint.")]
    rows = [[k, fmt(q[k]["n"]), f"{q[k]['ok_pct']}%", f"{q[k]['alive_pct']}%"] for k in sorted(q)]
    b += [("h2", "Newer entries are more likely to be alive"),
      ("p", f"Grouping non-bulk endpoints by the quarter the entry was first published, the share that answered at all rises broadly (not strictly every quarter), from {q[first_q]['alive_pct']}% for {first_q} to {q[last_q]['alive_pct']}% for {last_q}. The share that works without auth rises from {q[first_q]['ok_pct']}% to {q[last_q]['ok_pct']}%. This is a correlation: old entries may have been abandoned, or the registry may simply keep dead entries longer than live ones, and newer entries have had less time to break. We cannot tell these apart from one snapshot."),
      ("table", ["First published", "Endpoints", "Working", "Alive"], rows, (1, 2, 3)),
      ("p", f"Registry growth is steep: {fmt(qa['2026-Q3']['n'] + qa['2026-Q4']['n'])} of {fmt(N)} checked endpoints ({pct_(qa['2026-Q3']['n'] + qa['2026-Q4']['n'], N)}%) were first published in 2026-Q3 or 2026-Q4.")]
    hrows = [[r["group"], r["n"], f"{r['ok_pct']}%", f"{r['alive_pct']}%", (f"{r['latency_ok']['median']} ms" if r['latency_ok']['n'] >= 30 else "n<30")] for r in R["hosting"]["non_bulk"] if r["n"] >= 100]
    own = pf["own/other domain"]; plat = pf["platform subdomain"]
    b += [("h2", "Where servers run"),
      ("p", f"Outside the bulk namespaces, endpoints on the publisher's own (or otherwise unclassified) domain were alive {own['alive_pct']}% of the time, against {plat['alive_pct']}% for endpoints on a shared platform subdomain such as workers.dev, vercel.app or railway.app (n={fmt(own['n'])} and {fmt(plat['n'])}). The spread between platforms is wide: Vercel {hs['Vercel (*.vercel.app)']['alive_pct']}% alive, Render {hs['Render (*.onrender.com)']['alive_pct']}%, Railway {hs['Railway (*.railway.app)']['alive_pct']}%, Cloudflare Workers {hs['Cloudflare Workers (*.workers.dev)']['alive_pct']}%, Cloudflare Pages {hs['Cloudflare Pages (*.pages.dev)']['alive_pct']}%. Apify's {fmt(hs['Apify (*.apify.com)']['n'])} endpoints are all behind auth, so they look 'not working' but are alive. Hosting type is confounded with who publishes and when; we make no claim that a platform causes uptime."),
      ("table", ["Host type (non-bulk)", "Endpoints", "Working", "Alive", "Median latency"], hrows, (1, 2, 3, 4)),
      ("p", f"Working servers answered the handshake in a median {R['latency_bulk']['median']} ms for bulk publishers and {R['latency_non_bulk']['median']} ms for everyone else (p90 {R['latency_bulk']['p90']} and {R['latency_non_bulk']['p90']} ms), measured from a single location.")]
    b += [("h2", "Packages, repositories and a reversed gap"),
      ("p", f"{fmt(pk_all['packages + remote']['n'])} endpoints belong to entries that list an installable package as well as the remote ({fmt(pk_all['remote only']['n'])} are remote-only). Across all endpoints the package-plus-remote group works more often ({pk_all['packages + remote']['ok_pct']}% vs {pk_all['remote only']['ok_pct']}%). Excluding bulk publishers the order flips ({pk_nb['packages + remote']['ok_pct']}% vs {pk_nb['remote only']['ok_pct']}%), a reminder that composition effects can invert a comparison. Package-backed entries also expose far more tools: median {fmt(int(T['tools_median_with_packages']))} vs {fmt(int(T['tools_median_remote_only']))} for remote-only.")]
    tb = T["buckets"]
    b += [("h2", "Protocol versions, tools and errors"),
      ("p", f"We requested protocol version 2025-06-18, and servers reply with the version they will use, so this is not a survey of each server's newest supported version. Of {fmt(P['ok_n'])} working servers, {P['same_as_requested_pct']}% answered 2025-06-18, {P['older_pct']}% answered an older version and {P['newer_pct']}% a newer one."),
      ("table", ["protocolVersion returned", "Servers", "Share"], [[k, v, f"{P['pct'][k]}%"] for k, v in P["counts"].items()], (1, 2)),
      ("p", f"Among the {fmt(T['n'])} working servers that returned a tool list, the median is {fmt(int(T['median']))} tools and the mean {T['mean']}; {T['servers_over_50_pct']}% expose more than 50. The largest is {T['top10'][0]['name']} with {T['top10'][0]['tools']} tools, followed by {T['top10'][1]['name']} ({T['top10'][1]['tools']}) and {T['top10'][2]['name']} ({T['top10'][2]['tools']})."),
      ("bar", [(x["bucket"], x["n"]) for x in tb], f"Working servers by tool count (n={fmt(T['n'])})"),
      ("p", f"Among the {fmt(E['http_error_n'])} endpoints that failed with an HTTP status, 404 is the most common at {E['top_http_status'][0]['pct_of_http_errors']}% ({fmt(E['top_http_status'][0]['n'])}), and 404 plus 410 together account for {fmt(E['status_404_410_n'])} endpoints that no longer appear to exist. {fmt(E['status_402_n'])} endpoints returned 402 Payment Required."),
      ("table", ["HTTP status", "Endpoints", "% of HTTP errors"], [[x["status"], x["n"], f"{x['pct_of_http_errors']}%"] for x in E["top_http_status"]], (1, 2))]
    b += [("h2", "Methodology and limitations"),
      ("p", f"One attempt per endpoint on {d}, from one network location, with a 10-second timeout and one initialize request using protocol version 2025-06-18; only the first remote URL of each entry is checked, and only servers that worked without auth are asked for a tool list (first page only). A single check cannot separate permanent from transient failure. {fmt(E['tunnel_502_errors_n'])} failures ({E['tunnel_502_errors_pct_of_all']}% of all endpoints) carry an error message from the connection path (a tunnel 502) that may stem from the checking environment rather than the server, so failure rates are upper bounds. 'Auth required' servers are alive but unverified. Bulk publisher means a namespace with {R['generated_from']['bulk_publisher_min_urls']} or more checked endpoints; the threshold is our choice. Registry categories and repository fields are self-reported by publishers. All findings are correlations on one snapshot; the registry is a self-selected population and not a sample of all MCP servers.")]
    return heads, b

def _html(blocks):
    out = []
    for blk in blocks:
        if blk[0] == "h2": out.append(f"<h2>{e(blk[1])}</h2>")
        elif blk[0] == "p": out.append(f"<p>{blk[1]}</p>")
        elif blk[0] == "table": out.append(table(blk[1], blk[2], blk[3]))
        elif blk[0] == "bar": out.append(hbar(blk[1], blk[2]))
    return "\n".join(out)

def build(upd, day):
    R = json.load(open(f"data/reports/{SLUG}.json"))
    os.makedirs(f"{OUT}/data", exist_ok=True)
    shutil.copy(f"data/reports/{SLUG}.json", f"{OUT}/data/report-{SLUG}.json")
    d = R["generated_from"]["checked_date"]
    heads, blocks = content(R)
    url = f"{BASE_URL}/reports/{SLUG}/"
    cite = f"Agent Web Census, “{TITLE}”, {url}, based on a liveness check of {fmt(R['generated_from']['urls_checked'])} remote MCP servers on {d}. Data: {BASE_URL}/data/report-{SLUG}.json (CC BY 4.0)."
    body = f"""<h1>{e(TITLE)}</h1>
<p class="meta">Published {e(d)} · by an AI agent (Claude) · data: <a href="/data/report-{SLUG}.json">report-{SLUG}.json</a></p>
<div class="cite"><b>Headline findings</b><ol class="facts">{''.join(f'<li>{e(h)}</li>' for h in heads)}</ol></div>
{_html(blocks)}
{cite_box(e(cite))}
<p class="meta"><b>Authorship.</b> {e(AI_NOTE)} Reproduce: <code>python3 scripts/analyses/mcp_health_report.py</code>. Raw data: <a href="/data/health-servers.json">health-servers.json</a>.</p>"""
    page(f"/reports/{SLUG}/", f"{TITLE}: {R['overall']['alive_pct']}% alive, {R['overall']['ok_pct']}% work without auth",
         f"Data analysis of {fmt(R['generated_from']['urls_checked'])} remote MCP servers from the official registry, checked {d}: liveness by age, host, publisher concentration, protocol versions and tools.",
         body, d, {"@context": "https://schema.org", "@type": "Article", "headline": TITLE, "datePublished": d, "dateModified": d, "url": url,
                   "author": {"@type": "Organization", "name": SITE_NAME}, "license": "https://creativecommons.org/licenses/by/4.0/"})
    idx = f"""<h1>Reports</h1><p>Long-form analyses written by an AI agent (Claude) from the Agent Web Census data. Every number is computed by a script in the repository.</p>
<ul><li><a href="/reports/{SLUG}/">{e(TITLE)}</a> <span class="meta">({e(d)})</span>: {e(heads[0])}</li></ul>"""
    page("/reports/", "Reports: Agent Web Census", "Data-driven reports on the agent-facing web and the MCP ecosystem.", idx, d)

def devto(path):
    R = json.load(open(f"data/reports/{SLUG}.json")); d = R["generated_from"]["checked_date"]
    heads, blocks = content(R)
    import re
    md = lambda s: re.sub(r"</?code>", "`", re.sub(r"</?b>", "**", s))
    L = ["---", f"title: {TITLE}", "published: false", "tags: mcp, ai, webdev, opensource", f"canonical_url: {BASE_URL}/reports/{SLUG}/", "---", "",
         "Disclosure: this article and the underlying census were produced by an AI agent (Claude) in an experiment; a human sponsor published it.", "",
         "## Headline findings", ""] + [f"{i}. {h}" for i, h in enumerate(heads, 1)] + [""]
    for blk in blocks:
        if blk[0] == "h2": L += [f"## {blk[1]}", ""]
        elif blk[0] == "p": L += [md(blk[1]), ""]
        elif blk[0] in ("table", "bar"):
            hdr, rows = (blk[1], blk[2]) if blk[0] == "table" else (["Item", "Endpoints"], [[k, v] for k, v in blk[1]])
            if blk[0] == "bar": L += [f"*{blk[2]}*", ""]
            L += ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)] + ["| " + " | ".join(fmt(c) if not isinstance(c, str) else c for c in r) + " |" for r in rows] + [""]
    L += [f"Cite: Agent Web Census, \"{TITLE}\", {BASE_URL}/reports/{SLUG}/. Data (CC BY 4.0): {BASE_URL}/data/report-{SLUG}.json. Code: https://github.com/jirizaloudek/agentwebcensus, `scripts/analyses/mcp_health_report.py`.", "", AI_NOTE, ""]
    open(path, "w").write("\n".join(L))

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--devto": devto(sys.argv[2])
    else:
        _d = json.load(open(f"data/reports/{SLUG}.json"))["generated_from"]["checked_date"]; build(_d, _d)
