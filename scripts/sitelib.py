"""Tiny static-site helpers: page shell, SVG charts, number formatting. No dependencies."""
import html, json, os, datetime as dt
SITE_NAME = "Agent Web Census"
BASE_URL = os.environ.get("SITE_URL", "https://agentwebcensus.pages.dev").rstrip("/")
from urllib.parse import urlparse
PREFIX = urlparse(BASE_URL).path.rstrip("/")  # e.g. "/agentwebcensus" on a GitHub Pages project site, "" on own domain
CF_BEACON = os.environ.get("CF_BEACON_TOKEN", "")  # Cloudflare Web Analytics token
OUT = "site"
PAGES = []  # (path, lastmod) for sitemap
e = html.escape

def fmt(n):
    if isinstance(n, float): return f"{n:,.1f}"
    return f"{n:,}" if isinstance(n, int) else str(n)

CSS = """
:root{--fg:#111;--mut:#555;--bg:#fff;--acc:#2456c9;--bar:#3b6fe0;--line:#e5e7eb;--card:#f7f8fa}
@media (prefers-color-scheme:dark){:root{--fg:#eee;--mut:#aaa;--bg:#111418;--acc:#7aa2ff;--bar:#6f95f0;--line:#2a2f37;--card:#1a1e24}}
*{box-sizing:border-box}body{margin:0;font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--fg);background:var(--bg)}
main,header,footer{max-width:960px;margin:0 auto;padding:0 18px}header{padding-top:18px;display:flex;gap:18px;align-items:baseline;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:10px}
header a{color:var(--fg);text-decoration:none}header .brand{font-weight:700;font-size:1.15em}header nav a{margin-right:14px;color:var(--mut)}
a{color:var(--acc)}h1{font-size:1.9em;line-height:1.2;margin:24px 0 6px}h2{margin-top:34px;border-bottom:1px solid var(--line);padding-bottom:4px}
.meta{color:var(--mut);font-size:.9em}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:18px 0}
.kpi{background:var(--card);border-radius:10px;padding:12px 14px}.kpi b{display:block;font-size:1.7em;line-height:1.2}.kpi span{color:var(--mut);font-size:.88em}
table{border-collapse:collapse;width:100%;margin:10px 0;font-size:.95em}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.facts li{margin:6px 0}.cite{background:var(--card);border-left:3px solid var(--acc);padding:8px 12px;font-size:.9em;margin:16px 0}
svg text{fill:var(--fg);font-size:12px}svg .bar{fill:var(--bar)}svg .ax{stroke:var(--line)}footer{margin-top:50px;padding:18px;border-top:1px solid var(--line);color:var(--mut);font-size:.88em}
code{background:var(--card);padding:1px 5px;border-radius:4px}
"""

def page(path, title, desc, body, updated, jsonld=None):
    """path like '/mcp/' -> site/mcp/index.html"""
    url = BASE_URL + path
    beacon = (f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon=\'{{"token": "{CF_BEACON}"}}\'></script>' if CF_BEACON else "")
    ld = f'<script type="application/ld+json">{json.dumps(jsonld)}</script>' if jsonld else ""
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}"><link rel="canonical" href="{url}">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:type" content="article">
<meta name="robots" content="index,follow,max-snippet:-1"><link rel="alternate" type="text/plain" href="{BASE_URL}/llms.txt" title="llms.txt">
<style>{CSS}</style>{ld}</head><body>
<header><a class="brand" href="/">{SITE_NAME}</a><nav><a href="/mcp/">MCP servers</a><a href="/ai-crawlers/">AI crawlers</a><a href="/data/">Data &amp; API</a><a href="/about/">About</a></nav></header>
<main>{body}
<p class="meta">Last updated: <time datetime="{updated}">{updated}</time> (UTC). Numbers are recomputed automatically from primary sources; see <a href="/about/#methodology">methodology</a>.</p>
</main><footer>{SITE_NAME} is built and operated by an AI agent (Claude, by Anthropic) with a human sponsor. All data is open (CC BY 4.0). Corrections: open an issue on GitHub.</footer>{beacon}</body></html>"""
    if PREFIX:
        doc = doc.replace('href="/', f'href="{PREFIX}/').replace("href='/", f"href='{PREFIX}/")
    fp = os.path.join(OUT, path.strip("/"), "index.html") if path.endswith("/") else os.path.join(OUT, path.strip("/"))
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    open(fp, "w").write(doc)
    PAGES.append((path, updated[:10]))

def kpis(items):
    return '<div class="kpis">' + "".join(f'<div class="kpi"><b>{e(fmt(v))}</b><span>{e(l)}</span></div>' for v, l in items) + "</div>"

def table(headers, rows, num_cols=()):
    h = "".join(f'<th class="{"n" if i in num_cols else ""}">{e(x)}</th>' for i, x in enumerate(headers))
    b = "".join("<tr>" + "".join(f'<td class="{"n" if i in num_cols else ""}">{c if str(c).startswith("<a") else e(fmt(c))}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f"<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>"

def hbar(items, title, unit=""):
    """items: [(label, value)] horizontal bar chart SVG"""
    if not items: return ""
    w, lh, lw = 640, 24, 210
    mx = max(v for _, v in items) or 1
    hgt = lh * len(items) + 10
    rows = []
    for i, (l, v) in enumerate(items):
        y = i * lh + 4; bw = (w - lw - 90) * v / mx
        rows.append(f'<text x="{lw-6}" y="{y+15}" text-anchor="end">{e(str(l))[:32]}</text><rect class="bar" x="{lw}" y="{y+3}" width="{bw:.1f}" height="16" rx="2"/><text x="{lw+bw+6:.1f}" y="{y+15}">{e(fmt(v))}{unit}</text>')
    return f'<figure><svg viewBox="0 0 {w} {hgt}" width="100%" role="img" aria-label="{e(title)}"><title>{e(title)}</title>{"".join(rows)}</svg></figure>'

def vbar(items, title):
    """items [(label, value)] vertical bar chart (time series)"""
    if not items: return ""
    w, h, pad = 900, 240, 30
    mx = max(v for _, v in items) or 1
    bw = (w - pad) / len(items)
    out = []
    for i, (l, v) in enumerate(items):
        bh = (h - 50) * v / mx; x = pad + i * bw; y = h - 25 - bh
        out.append(f'<rect class="bar" x="{x+1:.1f}" y="{y:.1f}" width="{max(bw-2,1):.1f}" height="{bh:.1f}"><title>{e(str(l))}: {fmt(v)}</title></rect>')
        if len(items) <= 24 or i % max(1, len(items)//12) == 0:
            out.append(f'<text x="{x+bw/2:.1f}" y="{h-8}" text-anchor="middle">{e(str(l))}</text>')
    out.append(f'<text x="{pad}" y="14">max {fmt(mx)}</text><line class="ax" x1="{pad}" y1="{h-25}" x2="{w}" y2="{h-25}"/>')
    return f'<figure><svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{e(title)}"><title>{e(title)}</title>{"".join(out)}</svg></figure>'

def cite_box(text):
    return f'<div class="cite"><b>Cite this:</b> {text}</div>'

def write_sitemap():
    xs = "".join(f"<url><loc>{BASE_URL}{p}</loc><lastmod>{d}</lastmod></url>" for p, d in PAGES)
    open(os.path.join(OUT, "sitemap.xml"), "w").write(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{xs}</urlset>')
    open(os.path.join(OUT, "robots.txt"), "w").write(f"# AI agents and crawlers are welcome here. Data is CC BY 4.0.\nUser-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n")
