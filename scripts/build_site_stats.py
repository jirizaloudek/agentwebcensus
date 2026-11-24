"""Economic indicator pages (/stats/...): latest official numbers per country, for humans and AI agents.
Input: data/stats/latest.json (scripts/fetch_indicators.py). Output: HTML pages + .md twins + per-series JSON."""
import json, os, re, statistics
from sitelib import *
import sitelib

# indicator order on pages; (key, short label, slug)
IND = [("inflation", "Inflation (CPI)", "inflation"), ("policy_rate", "Central bank policy rate", "interest-rate"),
       ("unemployment", "Unemployment rate", "unemployment"), ("gdp_growth", "GDP growth (y/y, quarterly)", "gdp-growth"),
       ("inflation_hicp", "Inflation (HICP, EU harmonised)", "inflation-hicp"),
       ("imf_gdp_growth", "GDP growth, annual (IMF incl. forecast)", "gdp-growth-forecast"),
       ("imf_inflation", "Inflation, annual (IMF incl. forecast)", "inflation-forecast"), ("population", "Population", "population")]
LABEL = {k: l for k, l, _ in IND}
SLUG = {k: s for k, _, s in IND}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower().replace("&", "and").replace("'", "")).strip("-")


def period_h(p):
    """'2026-10' -> 'October 2026', '2026-Q3' -> 'Q3 2026', '2026-11-20' -> '20 November 2026'"""
    p = str(p)
    m = re.fullmatch(r"(\d{4})-(\d{2})", p)
    if m: return f"{MONTHS[int(m[2]) - 1]} {m[1]}"
    m = re.fullmatch(r"(\d{4})-Q(\d)", p)
    if m: return f"Q{m[2]} {m[1]}"
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", p)
    if m: return f"{int(m[3])} {MONTHS[int(m[2]) - 1]} {m[1]}"
    return p


def val_h(k, v, unit):
    if v is None: return "–"
    if k == "population": return f"{int(v):,}"
    return f"{v:.2f}".rstrip("0").rstrip(".") + (unit if unit == "%" else (" " + unit if unit else ""))


def chart(obs, title, unit):
    """bar chart with negative support. obs [(period, value, ...)]"""
    obs = [o for o in obs if o[1] is not None][-36:]
    if len(obs) < 2: return ""
    w, h, padl, padb = 900, 230, 40, 26
    vs = [o[1] for o in obs]
    hi, lo = max(max(vs), 0), min(min(vs), 0)
    rng = (hi - lo) or 1
    y0 = 12 + (h - padb - 12) * hi / rng
    bw = (w - padl) / len(obs)
    out = [f'<line class="ax" x1="{padl}" y1="{y0:.1f}" x2="{w}" y2="{y0:.1f}"/>',
           f'<text x="0" y="14">{e(val_h("", hi, unit))}</text><text x="0" y="{h - padb:.0f}">{e(val_h("", lo, unit))}</text>']
    for i, o in enumerate(obs):
        p, v = o[0], o[1]
        bh = (h - padb - 12) * abs(v) / rng
        x = padl + i * bw
        y = y0 - bh if v >= 0 else y0
        fc = (o[2] if len(o) > 2 else False)
        out.append(f'<rect class="bar" x="{x + 1:.1f}" y="{y:.1f}" width="{max(bw - 2, 1):.1f}" height="{max(bh, .5):.1f}"{" opacity=.45" if fc else ""}><title>{e(period_h(p))}: {e(val_h("", v, unit))}{" (forecast)" if fc else ""}</title></rect>')
        if len(obs) <= 14 or i % max(1, len(obs) // 9) == 0 or i == len(obs) - 1:
            out.append(f'<text x="{x + bw / 2:.1f}" y="{h - 8}" text-anchor="middle">{e(str(p))}</text>')
    return f'<figure><svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{e(title)}"><title>{e(title)}</title>{"".join(out)}</svg></figure>'


def latest(s):
    """latest actual (non-forecast) observation and previous one"""
    obs = [o for o in s.get("obs", []) if o[1] is not None]
    act = [o for o in obs if not (len(o) > 2 and o[2])] or obs
    if not act: return None, None
    return act[-1], (act[-2] if len(act) > 1 else None)


def write_text(path, text):
    fp = os.path.join(OUT, path.lstrip("/"))
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    open(fp, "w").write(text)


def fact(cname, k, s, ind, day):
    cur, prev = latest(s)
    if not cur: return ""
    unit = ind.get("unit", "")
    src = s.get("source_name") or s.get("source", "")
    name = ind.get("name", LABEL.get(k, k))
    if k == "population":
        return f"{cname}: population {val_h(k, cur[1], '')} ({cur[0]}; source: {src})."
    daily = len(str(cur[0])) == 10
    t = f"{cname}: {name} = {val_h(k, cur[1], unit)} {'as of' if daily else 'in'} {period_h(cur[0])}"
    if prev and not daily: t += f" (previous: {val_h(k, prev[1], unit)} in {period_h(prev[0])})"
    lc = s.get("last_change") if k == "policy_rate" else None
    if isinstance(lc, dict) and lc.get("date"):
        t += f"; last changed on {period_h(lc['date'])} (from {val_h(k, lc.get('from'), unit)} to {val_h(k, lc.get('to'), unit)})"
    if k == "policy_rate" and s.get("latest_daily"):
        t += f"; daily value as of {period_h(s['latest_daily'][0])}: {val_h(k, s['latest_daily'][1], unit)}"
    if s.get("note"): t += f" [{s['note']}]"
    fc = [o for o in s.get("obs", []) if len(o) > 2 and o[2] and o[1] is not None]
    if fc: t += "; IMF projections: " + ", ".join(f"{o[0]}: {val_h(k, o[1], unit)}" for o in fc)
    return t + f". Source: {src}; retrieved {s.get('fetched', day)}."


def md_doc(title, intro, lines, url, upd):
    return (f"# {title}\n\n{intro}\n\n" + "\n".join(lines) +
            f"\n\nCanonical URL: {url}\nUpdated: {upd} UTC (refreshed daily from official sources). Data: CC BY 4.0, cite \"datacensus.org\" with the URL. "
            f"Upstream licences apply (OECD, BIS, IMF, World Bank, Eurostat: free reuse with attribution).\n")


def build(upd, day):
    D = json.load(open("data/stats/latest.json"))
    I, C, S = D["indicators"], D["countries"], D["series"]
    gen = D.get("generated", upd)
    keys = [k for k, _, _ in IND if k in I and any(k in S.get(c, {}) for c in S)]
    cslug = {c: slugify(C.get(c, {}).get("name", c)) for c in S}
    cname = {c: C.get(c, {}).get("name", c) for c in S}
    os.makedirs(OUT + "/data/stats", exist_ok=True)
    json.dump(D, open(OUT + "/data/stats-latest.json", "w"), separators=(",", ":"))

    # compact latest table (agents: one fetch answers "latest X for every country")
    flat = {}
    for c, ser in S.items():
        row = {"name": cname[c], "iso3": c if len(c) == 3 else None, "iso2": C.get(c, {}).get("iso2"), "url": f"{BASE_URL}/stats/{cslug[c]}/"}
        for k in keys:
            if k in ser:
                cur, prev = latest(ser[k])
                if cur: row[k] = {"value": cur[1], "period": cur[0], "previous": prev[1] if prev else None, "source": ser[k].get("source")}
        flat[c] = row
    json.dump({"generated": gen, "license": "CC BY 4.0 (cite datacensus.org); upstream: OECD, BIS, IMF, World Bank, Eurostat", "indicators": {k: I[k] for k in keys}, "countries": flat},
              open(OUT + "/data/stats-summary.json", "w"), separators=(",", ":"))

    # ---- per country × indicator
    for c, ser in S.items():
        cn, cs = cname[c], cslug[c]
        for k in keys:
            if k not in ser: continue
            s, ind = ser[k], I[k]
            cur, prev = latest(s)
            if not cur: continue
            unit = ind.get("unit", "")
            path = f"/stats/{cs}/{SLUG[k]}/"
            obs = s["obs"]
            json.dump({"country": cn, "code": c, "indicator": k, **ind, **{x: s.get(x) for x in ("source", "source_name", "source_url", "fetched", "last_updated_by_source", "last_change")},
                       "latest": {"period": cur[0], "value": cur[1]}, "obs": obs, "canonical": BASE_URL + path, "generated": gen},
                      open(f"{OUT}/data/stats/{c}-{k}.json", "w"), separators=(",", ":"))
            f = fact(cn, k, s, ind, day)
            title = f"{cn} {LABEL[k].lower() if k != 'population' else 'population'}: {val_h(k, cur[1], unit)} ({period_h(cur[0])})"
            rows = [[period_h(o[0]) + (" (forecast)" if len(o) > 2 and o[2] else ""), val_h(k, o[1], unit)] for o in reversed(obs)]
            src = f'<a href="{e(s.get("source_url", "#"))}">{e(s.get("source_name") or s.get("source", ""))}</a>'
            other = " · ".join(f'<a href="/stats/{cs}/{SLUG[x]}/">{e(LABEL[x])}</a>' for x in keys if x in ser and x != k)
            body = f"""<p class="meta"><a href="/stats/">Economic indicators</a> › <a href="/stats/{cs}/">{e(cn)}</a></p>
<h1>{e(cn)}: {e(ind.get('name', LABEL[k]))}</h1>
{kpis([(val_h(k, cur[1], unit), 'latest · ' + period_h(cur[0])), (val_h(k, prev[1], unit) if prev else '–', 'previous · ' + (period_h(prev[0]) if prev else '–'))])}
<p class="facts">{e(f)}</p>
{chart(obs, title, unit)}
<h2>History</h2>{table(['Period', ind.get('name', LABEL[k])], rows[:60], num_cols=(1,))}
<h2>Source &amp; method</h2><p>Official data from {src}, retrieved automatically every day (last retrieval {e(s.get('fetched', day))}). {e(ind.get('note', ''))}
We republish the official figure unchanged; when the source revises a number, this page follows. Values are as published by the source and may lag national releases by days to weeks.</p>
<p>Machine-readable: <a href="/data/stats/{c}-{k}.json">JSON</a> · <a href="index.md">Markdown</a> · <a href="/data/stats-summary.json">all countries (JSON)</a></p>
{cite_box(f'datacensus.org, “{e(cn)} – {e(LABEL[k])}”, {BASE_URL}{path}, retrieved {day}. Underlying data: {e(s.get("source_name") or s.get("source", ""))}.')}
<p>More for {e(cn)}: {other} · Compare: <a href="/stats/{SLUG[k]}/">{e(LABEL[k])} by country</a></p>"""
            ld = {"@context": "https://schema.org", "@type": "Dataset", "name": f"{cn} – {ind.get('name', LABEL[k])}", "description": f,
                  "url": BASE_URL + path, "license": "https://creativecommons.org/licenses/by/4.0/", "dateModified": gen[:10],
                  "isBasedOn": s.get("source_url"), "creator": {"@type": "Organization", "name": "datacensus.org"},
                  "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{BASE_URL}/data/stats/{c}-{k}.json"}]}
            page(path, title + " – latest official data", f, body, upd, ld)
            write_text(path + "index.md", md_doc(f"{cn}: {ind.get('name', LABEL[k])}", f,
                       ["| Period | Value |", "|---|---|"] + [f"| {r[0]} | {r[1]} |" for r in rows[:60]] + ["", f"Source: {s.get('source_name') or s.get('source')} ({s.get('source_url', '')})"], BASE_URL + path, upd))

    # ---- country pages
    for c, ser in S.items():
        cn, cs = cname[c], cslug[c]
        ks = [k for k in keys if k in ser and latest(ser[k])[0]]
        if not ks: continue
        facts = [fact(cn, k, ser[k], I[k], day) for k in ks]
        rows = []
        for k in ks:
            cur, prev = latest(ser[k])
            rows.append([f'<a href="/stats/{cs}/{SLUG[k]}/">{e(LABEL[k])}</a>', val_h(k, cur[1], I[k].get("unit", "")), period_h(cur[0]),
                         val_h(k, prev[1], I[k].get("unit", "")) if prev else "–", ser[k].get("source", "")])
        path = f"/stats/{cs}/"
        body = f"""<p class="meta"><a href="/stats/">Economic indicators</a></p><h1>{e(cn)}: latest economic indicators</h1>
<p>The most recent official figures for {e(cn)}, refreshed daily from OECD, BIS, IMF, World Bank and Eurostat.</p>
{table(['Indicator', 'Latest', 'Period', 'Previous', 'Source'], rows, num_cols=(1, 3))}
<h2>Key facts</h2><ul class="facts">{''.join(f'<li>{e(x)}</li>' for x in facts)}</ul>
<p>Machine-readable: <a href="index.md">Markdown</a> · <a href="/data/stats-summary.json">all countries (JSON)</a></p>"""
        page(path, f"{cn} economy: inflation, interest rate, unemployment, GDP – latest data", f"Latest official economic indicators for {cn}: " + "; ".join(facts[:2]), body, upd)
        write_text(path + "index.md", md_doc(f"{cn}: latest economic indicators", f"Latest official values for {cn} (inflation, central bank policy rate, unemployment, GDP growth, IMF forecasts, population), each with its reference period, previous value and primary source. Refreshed daily.", [f"- {x}" for x in facts], BASE_URL + path, upd))

    # ---- indicator ranking pages
    for k in keys:
        ind, unit = I[k], I[k].get("unit", "")
        rows, md = [], []
        for c, ser in S.items():
            if k not in ser: continue
            cur, prev = latest(ser[k])
            if not cur: continue
            rows.append((cur[1], c, cur, prev))
        rows.sort(key=lambda r: -r[0])
        vals = [r[0] for r in rows if len(r[1]) == 3]
        tr = [[f'<a href="/stats/{cslug[c]}/{SLUG[k]}/">{e(cname[c])}</a>', val_h(k, cur[1], unit), period_h(cur[0]), val_h(k, prev[1], unit) if prev else "–"] for _, c, cur, prev in rows]
        md = ["| Country | Latest | Period | Previous |", "|---|---|---|---|"] + [f"| {cname[c]} | {val_h(k, cur[1], unit)} | {period_h(cur[0])} | {val_h(k, prev[1], unit) if prev else '–'} |" for _, c, cur, prev in rows]
        summ = f"{len(rows)} countries/areas. " + (f"Median {val_h(k, statistics.median(vals), unit)}; highest {cname[rows[0][1]]} ({val_h(k, rows[0][0], unit)}), lowest {cname[rows[-1][1]]} ({val_h(k, rows[-1][0], unit)})." if vals else "")
        path = f"/stats/{SLUG[k]}/"
        title = f"{LABEL[k]} by country – latest official data ({day[:7]})"
        body = f"""<p class="meta"><a href="/stats/">Economic indicators</a></p><h1>{e(ind.get('name', LABEL[k]))} by country</h1>
<p>{e(summ)} Each row shows the most recent figure published by the official source; reference periods differ between countries.</p>
{table(['Country', 'Latest', 'Period', 'Previous'], tr, num_cols=(1, 3))}
<p>{e(ind.get('note', ''))} Machine-readable: <a href="index.md">Markdown</a> · <a href="/data/stats-summary.json">JSON</a></p>"""
        page(path, title, f"{ind.get('name', LABEL[k])} for {len(rows)} countries, latest official values. {summ}", body, upd)
        write_text(path + "index.md", md_doc(f"{ind.get('name', LABEL[k])} by country", summ, md, BASE_URL + path, upd))

    # ---- hub
    hdr = ["Country"] + [LABEL[k].split(" (")[0] for k in keys if k in ("inflation", "policy_rate", "unemployment", "gdp_growth", "population")]
    hk = [k for k in keys if k in ("inflation", "policy_rate", "unemployment", "gdp_growth", "population")]
    big = sorted(S, key=lambda c: -(latest(S[c].get("population", {}))[0] or [0, 0])[1])
    rows = []
    for c in big:
        if not any(k in S[c] for k in hk if k != "population"): continue
        r = [f'<a href="/stats/{cslug[c]}/">{e(cname[c])}</a>']
        for k in hk:
            cur = latest(S[c][k])[0] if k in S[c] else None
            r.append(val_h(k, cur[1], I[k].get("unit", "")) if cur else "–")
        rows.append(r)
    links = " · ".join(f'<a href="/stats/{SLUG[k]}/">{e(LABEL[k])}</a>' for k in keys)
    body = f"""<h1>Latest economic indicators by country</h1>
<p>Inflation, central bank interest rates, unemployment, GDP growth and population for {len(rows)} economies — the most recent <b>official</b> figures,
re-fetched every day from OECD, the Bank for International Settlements, the IMF, the World Bank and Eurostat. Built for people and for AI agents: every number has a period, a source and a stable URL, plus Markdown and JSON versions.</p>
<p>By indicator: {links}</p>
{table(hdr, rows, num_cols=tuple(range(1, len(hdr))))}
<h2>For AI agents &amp; developers</h2><ul><li><a href="/data/stats-summary.json">/data/stats-summary.json</a> — latest value of every indicator for every country (one request).</li>
<li><code>/data/stats/&lt;ISO3&gt;-&lt;indicator&gt;.json</code> — full series, e.g. <a href="/data/stats/USA-inflation.json">USA-inflation.json</a>.</li>
<li>Every page has a Markdown twin (<code>index.md</code>). MCP: tool <code>latest_indicator</code> on <a href="https://datacensus.org/mcp">datacensus.org/mcp</a>.</li></ul>
<p class="meta">Figures are republished unchanged from the sources; reference periods differ by country and may lag national statistical releases. Not financial advice.</p>"""
    page("/stats/", "Latest economic indicators by country: inflation, interest rates, unemployment, GDP", f"Latest official inflation, policy rates, unemployment and GDP growth for {len(rows)} economies, refreshed daily from OECD, BIS, IMF, World Bank, Eurostat.", body, upd)
    write_text("/stats/index.md", md_doc("Latest economic indicators by country", "Refreshed daily from OECD, BIS, IMF, World Bank, Eurostat.",
               ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)] + ["| " + " | ".join(re.sub(r"<[^>]+>", "", x) for x in r) + " |" for r in rows] +
               ["", "Indicators: " + ", ".join(f"{LABEL[k]}: {BASE_URL}/stats/{SLUG[k]}/" for k in keys)], BASE_URL + "/stats/", upd))
    return {"countries": len(rows), "keys": keys, "facts": [fact(cname[c], "inflation", S[c]["inflation"], I["inflation"], day) for c in ("USA", "EA20", "GBR", "JPN", "CHN") if c in S and "inflation" in S[c]]}
