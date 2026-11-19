"""MCP liveness pages: /mcp/health/ and /mcp/health/working/."""
import shutil, datetime as dt
from sitelib import *

LABEL = {"ok": "Working (initialize OK, no auth)", "auth_required": "Auth required (alive)", "http_error": "HTTP error", "timeout": "Timeout",
         "dns_error": "DNS error", "tls_error": "TLS error", "conn_error": "Connection error", "invalid_response": "Invalid response"}

def build(H, servers_health, upd, day):
    for src, dst in (("data/health/latest.json", "health-latest.json"), ("data/health/servers.json", "health-servers.json")):
        shutil.copy(src, f"{OUT}/data/{dst}")
    gen = H["generated"]; mon = dt.date.fromisoformat(gen).strftime("%b %Y"); N = H["checked"]; T = H["totals"]; L = H["latency_ms_ok"]; TL = H["tools"]
    scope = f"remote servers in the official MCP Registry checked on {gen}"
    den = f"of the {fmt(N)} {scope}"
    ok, au = T["ok"], T["auth_required"]
    bad = N - ok["n"] - au["n"]
    facts = [
      f"As of {gen}, {ok['pct_of_checked']}% {den} ({fmt(ok['n'])}) completed an MCP initialize handshake without authentication.",
      f"As of {gen}, a further {au['pct_of_checked']}% {den} ({fmt(au['n'])}) answered but require authentication (HTTP 401/403 or WWW-Authenticate), so {H['alive_pct_of_checked']}% are alive in total.",
      f"As of {gen}, {pct_(bad, N)}% {den} ({fmt(bad)}) failed with an HTTP error, timeout, DNS, TLS, connection or invalid-response error on a single attempt.",
      f"As of {gen}, among the {fmt(L['n'])} servers that answered initialize without authentication, median initialize latency was {fmt(L['median'])} ms and p90 {fmt(L['p90'])} ms.",
      f"As of {gen}, among the {fmt(TL['n_with_count'])} working servers that returned a tools/list, the median server exposes {fmt(TL['median'])} tools (mean {fmt(TL['mean'])}).",
    ]
    CITE = f"Agent Web Census, “Do remote MCP servers actually work?”, {BASE_URL}/mcp/health/, check of {scope}."
    out_items = [(LABEL[o], T[o]["n"]) for o in T if T[o]["n"]]
    tb = [(k, v) for k, v in TL["buckets"].items()]
    pv = list(H["protocol_versions"].items())
    hosts = [[x["host"], x["servers"], f"{x['ok_pct']}%"] for x in H["top_hosts"]]
    defs = """<div class="cite"><b>Definitions</b><ul><li><b>Working</b>: the first remote URL answered one MCP <code>initialize</code> request with a valid result and no authentication was demanded.</li>
<li><b>Auth required</b>: HTTP 401/403 or a <code>WWW-Authenticate</code> header. The endpoint is alive but needs credentials; we do not know whether it works for authorised users.</li>
<li><b>Failed</b>: HTTP error (other 4xx/5xx), timeout (10 s), DNS, TLS or connection error, or a response that is not an MCP initialize result.</li>
<li>Legacy SSE-type remotes only get a reachability check (event stream starts within 5 s); they have no tool count or protocol version.</li></ul></div>"""
    body = f"""<h1>Do remote MCP servers actually work? ({mon})</h1>
<p class="meta">We sent one MCP initialize handshake to each {scope}; repeated weekly. {fmt(N)} URLs checked.</p>
{kpis([(f"{ok['pct_of_checked']}%", "work without auth"), (f"{au['pct_of_checked']}%", "alive but need auth"), (f"{pct_(bad, N)}%", "failed"), (f"{fmt(L['median'])} ms", "median initialize latency"), (TL['median'], "median tools per working server"), (N, "URLs checked")])}
<h2>Key facts</h2><ul class="facts">{''.join(f'<li>{e(f)}</li>' for f in facts)}</ul>{cite_box(e(CITE))}
{defs}
<h2>Outcome of the handshake</h2>{hbar(out_items, f'Outcome for {fmt(N)} remote MCP servers checked on {gen}')}
{table(['Outcome', 'Servers', '% of checked'], [[LABEL[o], T[o]['n'], f"{T[o]['pct_of_checked']}%"] for o in T], (1, 2))}
<h2>Tools per working server</h2>{hbar(tb, f"Servers by number of tools (n={fmt(TL['n_with_count'])})")}
<p class="meta">Median {fmt(TL['median'])}, mean {fmt(TL['mean'])}; only the first page of tools/list is counted, only for servers that worked without authentication.</p>
<h2>Latency</h2><p>Initialize round trip for {fmt(L['n'])} working servers: median <b>{fmt(L['median'])} ms</b>, p90 <b>{fmt(L['p90'])} ms</b>, measured from one network location including connection setup.</p>
<h2>Protocol versions</h2><p class="meta">Version the server answered with when our client requested <code>2025-06-18</code>. Per the MCP spec a server replies with the requested version if it supports it, so this shows how many servers support 2025-06-18 versus fall back to an older (or newer) version — not each server’s newest supported version.</p>{table(['protocolVersion returned', 'Servers'], [[k, v] for k, v in pv], (1,)) if pv else ''}
<h2>Biggest hosts</h2>{table(['Host', 'Servers checked', 'Working (no auth)'], hosts, (1, 2))}
<p class="meta">Top 20 hosts by number of registry servers checked; percentage is of that host’s servers.</p>
<p><a href="/mcp/health/working/">List of working servers →</a></p>
<h2 id="methodology">Methodology and caveats</h2><p class="meta">{e(H['methodology'])}</p>
<p>Data: <a href="/data/health-latest.json">health-latest.json</a> · <a href="/data/health-servers.json">health-servers.json</a></p>"""
    page("/mcp/health/", f"Do remote MCP servers actually work? ({mon}): {ok['pct_of_checked']}% answer, {au['pct_of_checked']}% need auth",
         f"We checked {fmt(N)} remote servers from the official MCP Registry on {gen}: {ok['pct_of_checked']}% completed an initialize handshake, {au['pct_of_checked']}% require auth, {pct_(bad, N)}% failed.", body, gen,
         {"@context": "https://schema.org", "@type": "Dataset", "name": "Liveness of remote MCP servers", "url": BASE_URL + "/mcp/health/", "dateModified": gen,
          "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": SITE_NAME},
          "distribution": [{"@type": "DataDownload", "encodingFormat": "json", "contentUrl": BASE_URL + "/data/health-latest.json"}]})

    wk = sorted([s for s in servers_health if s["outcome"] == "ok" and s.get("tools_count") is not None], key=lambda s: (-s["tools_count"], s["name"]))
    wn = sum(1 for s in servers_health if s["outcome"] == "ok")
    rows = [[s["name"], s["tools_count"], f"{s['latency_ms']} ms" if s.get("latency_ms") is not None else "–", s["url"]] for s in wk[:500]]
    body = f"""<h1>Remote MCP servers that answered without authentication ({mon})</h1>
<p>{fmt(wn)} of {fmt(N)} remote servers in the official MCP Registry completed an initialize handshake without authentication on {gen}; {fmt(len(wk))} of them returned a tool list. Showing the top {fmt(min(500, len(wk)))} by tool count.</p>
{table(['Server', 'Tools', 'Latency', 'URL'], rows, (1, 2))}
<p class="meta">Single check per week; a server missing here may have failed transiently. Full list: <a href="/data/health-servers.json">health-servers.json</a> · <a href="/data/health-latest.json">health-latest.json</a>. <a href="/mcp/health/">← back to the summary</a></p>"""
    page("/mcp/health/working/", f"Working remote MCP servers ({mon}): {fmt(wn)} answered an initialize handshake",
         f"{fmt(wn)} remote MCP servers from the official registry answered an unauthenticated initialize handshake on {gen}; top {min(500, len(wk))} by tool count.", body, gen)

pct_ = lambda a, b: round(100 * a / b, 1) if b else 0.0
