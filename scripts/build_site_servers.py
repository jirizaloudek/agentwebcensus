"""Per-server liveness pages: /mcp/server/<slug>/ ("Is <server> MCP server working?") and the A-Z index /mcp/servers/.
Deterministic on purpose: page HTML depends only on health records + registry text, never on the daily build timestamp (IndexNow hashes pages)."""
import re
from collections import OrderedDict
from sitelib import *

PER_INDEX = 2000
WORDS = {"ok": "Working", "auth_required": "Auth required", "http_error": "HTTP error", "timeout": "Timeout", "dns_error": "DNS error",
         "tls_error": "TLS error", "conn_error": "Connection error", "invalid_response": "Invalid response"}
FAIL = {"http_error": "an HTTP error", "timeout": "a timeout (no answer within 10 s)", "dns_error": "a DNS error (hostname did not resolve)",
        "tls_error": "a TLS/certificate error", "conn_error": "a connection error", "invalid_response": "a response that was not a valid MCP initialize result"}
RANK = {"ok": 0, "auth_required": 1}  # best outcome first; failures after

def slugify(n):
    return re.sub(r"[^a-z0-9.-]+", "-", n.lower()).strip("-.") or "server"

def trunc(s, n=500):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"

def ms(v): return f"{v} ms" if v is not None else "–"

def answer(name, eps):
    best = min(eps, key=lambda r: (RANK.get(r["outcome"], 2), r["url"]))
    o, d = best["outcome"], best["checked"]
    multi = f" (best of {len(eps)} endpoints)" if len(eps) > 1 else ""
    if o == "ok":
        t = best.get("tools_count")
        s = f"Yes — on {d} its remote endpoint answered an MCP initialize handshake" + (f" in {best['latency_ms']} ms" if best.get("latency_ms") is not None else "")
        s += f" and reported {t} tool{'s' if t != 1 else ''}." if t is not None else "."
        return s[:-1] + multi + "." if multi else s, "Yes"
    if o == "auth_required":
        h = f"HTTP {best['http_status']}" if best.get("http_status") else "an authentication challenge"
        return f"Requires authentication — on {d} it returned {h} without credentials{multi}; that usually means it is up but needs a key.", "Needs auth"
    extra = f" (HTTP {best['http_status']})" if o == "http_error" and best.get("http_status") else ""
    all_bad = "every endpoint" if len(eps) > 1 else "the endpoint"
    return f"No — on {d} {all_bad} failed with {FAIL.get(o, o)}{extra}. This was a single attempt and may be transient.", "No"

def build(health_servers, registry_servers, upd, day):
    reg = {s["name"]: s for s in (registry_servers or [])}
    groups = OrderedDict()
    for r in sorted(health_servers, key=lambda r: (r["name"], r["url"])):
        groups.setdefault(r["name"], []).append(r)
    used, entries = set(), []
    for name, eps in groups.items():
        sl = base = slugify(name); i = 2
        while sl in used:
            sl = f"{base}-{i}"; i += 1
        used.add(sl); entries.append((name, sl, eps))
    for name, sl, eps in entries:
        m = reg.get(name) or {}
        title = (m.get("title") or "").strip() or name
        day_ = max(r["checked"] for r in eps)
        ans, short = answer(name, eps)
        oks = [r for r in eps if r["outcome"] == "ok"]
        lat = [r["latency_ms"] for r in oks if r.get("latency_ms") is not None]
        tools = [r["tools_count"] for r in oks if r.get("tools_count") is not None]
        k = [(WORDS.get(min(eps, key=lambda r: (RANK.get(r["outcome"], 2), r["url"]))["outcome"], "?"), "outcome on " + day_),
             (len(eps), "endpoint" + ("s" if len(eps) != 1 else "") + " checked"), (ms(min(lat)) if lat else "–", "initialize latency"), (max(tools) if tools else "–", "tools reported")]
        rows = [[r["url"], WORDS.get(r["outcome"], r["outcome"]), r.get("http_status") if r.get("http_status") is not None else "–", ms(r.get("latency_ms")),
                 r["tools_count"] if r.get("tools_count") is not None else "–", r.get("protocol_version") or "–"] for r in eps]
        rows = [[e(str(c)) if i == 0 else c for i, c in enumerate(r)] for r in rows]
        meta = [f"<li>Registry name: <code>{e(name)}</code></li>"]
        if m.get("description"): meta.append(f"<li>Description (from the registry, not verified by us): {e(trunc(m['description']))}</li>")
        for key, lab in (("repository", "Repository"), ("website", "Website")):
            v = m.get(key)
            if isinstance(v, dict): v = v.get("url")
            if isinstance(v, str) and v.startswith(("https://", "http://")):
                meta.append(f'<li>{lab}: <a href="{e(v)}" rel="nofollow noopener">{e(trunc(v, 200))}</a></li>')
        if m.get("version"): meta.append(f"<li>Version: {e(trunc(m['version'], 60))}</li>")
        from urllib.parse import quote
        meta.append(f'<li><a href="https://registry.modelcontextprotocol.io/v0/servers?search={quote(name, safe="")}" rel="nofollow noopener">Look up in the official MCP Registry</a></li>')
        CITE = f"Agent Web Census, “Is {title} MCP server working?”, {BASE_URL}/mcp/server/{sl}/, liveness check of {day_}."
        body = f"""<h1>Is {e(title)} MCP server working?</h1>
<p><b>{e(ans)}</b></p>
{kpis(k)}
<h2>Endpoints checked</h2>{table(['URL', 'Outcome', 'HTTP status', 'Latency', 'Tools', 'Protocol version'], rows, (2, 3, 4))}
<h2>About this server</h2><ul class="facts">{''.join(meta)}</ul>
<p class="meta"><b>Note:</b> this is a single check made once a week from GitHub Actions (one MCP initialize request per endpoint, 10 s timeout), not continuous monitoring. A failure may be transient or specific to our network location; “auth required” means we could not test further without credentials. See <a href="/mcp/health/">MCP liveness statistics</a>, the <a href="/mcp/servers/">list of all checked servers</a> and the <a href="/about/#methodology">methodology</a>.</p>
{cite_box(e(CITE))}"""
        page(f"/mcp/server/{sl}/", f"Is {title} MCP server working? ({short}, checked {day_})",
             trunc(f"{ans} Weekly liveness check of the remote MCP server {name} from the official MCP Registry.", 300), body, day_,
             {"@context": "https://schema.org", "@type": "WebPage", "name": f"Is {title} MCP server working?", "url": f"{BASE_URL}/mcp/server/{sl}/",
              "dateModified": day_, "about": {"@type": "SoftwareApplication", "name": title, "applicationCategory": "MCP server"},
              "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": BASE_URL}})
    # ---- A-Z index, paginated ----
    pages = [entries[i:i + PER_INDEX] for i in range(0, len(entries), PER_INDEX)] or [[]]
    N = len(entries); lastd = max((r["checked"] for r in health_servers), default=day)
    for pi, chunk in enumerate(pages, 1):
        path = "/mcp/servers/" if pi == 1 else f"/mcp/servers/page/{pi}/"
        trs = "".join(f'<tr><td><a href="/mcp/server/{sl}/">{e(n)}</a></td><td>{WORDS.get(min(eps, key=lambda r: (RANK.get(r["outcome"], 2), r["url"]))["outcome"], "?")}</td></tr>' for n, sl, eps in chunk)
        nav = " · ".join(([f'<a href="{"/mcp/servers/" if pi == 2 else f"/mcp/servers/page/{pi-1}/"}">← previous</a>'] if pi > 1 else []) +
                         ([f'<a href="/mcp/servers/page/{pi+1}/">next →</a>'] if pi < len(pages) else []))
        body = f"""<h1>Is this MCP server working? All {fmt(N)} remote servers checked</h1>
<p>Alphabetical list of the remote MCP servers from the official MCP Registry that our weekly liveness check tested (latest check {lastd}). Click a name for its dated answer. Page {pi} of {len(pages)}.</p>
<table><thead><tr><th>Server</th><th>Outcome</th></tr></thead><tbody>{trs}</tbody></table>
<p>{nav}</p>
<p class="meta">Single weekly check from GitHub Actions, not continuous monitoring. <a href="/mcp/health/">← MCP liveness statistics</a> · <a href="/about/#methodology">methodology</a></p>"""
        page(path, f"Is this MCP server working? Status of {fmt(N)} remote MCP servers" + (f" (page {pi})" if pi > 1 else ""),
             f"Alphabetical list of {fmt(N)} remote MCP servers from the official registry with the result of our weekly liveness check ({lastd}).", body, lastd)
    return N
