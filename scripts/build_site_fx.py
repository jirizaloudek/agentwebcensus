"""/stats/fx/: ECB euro reference exchange rates (data/stats/fx.json, scripts/fetch_fx.py). Index + one page per currency (+ .md twins, JSON)."""
import json, os
from sitelib import *
import build_site_stats as bs

NAMES = {"USD": "US dollar", "JPY": "Japanese yen", "CZK": "Czech koruna", "DKK": "Danish krone", "GBP": "Pound sterling", "HUF": "Hungarian forint",
         "PLN": "Polish zloty", "RON": "Romanian leu", "SEK": "Swedish krona", "CHF": "Swiss franc", "ISK": "Icelandic krona", "NOK": "Norwegian krone",
         "TRY": "Turkish lira", "AUD": "Australian dollar", "BRL": "Brazilian real", "CAD": "Canadian dollar", "CNY": "Chinese yuan renminbi",
         "HKD": "Hong Kong dollar", "IDR": "Indonesian rupiah", "ILS": "Israeli shekel", "INR": "Indian rupee", "KRW": "South Korean won",
         "MXN": "Mexican peso", "MYR": "Malaysian ringgit", "NZD": "New Zealand dollar", "PHP": "Philippine peso", "SGD": "Singapore dollar",
         "THB": "Thai baht", "ZAR": "South African rand", "BGN": "Bulgarian lev"}


def fmt(v):
    return f"{v:.4f}" if v < 100 else f"{v:.2f}"


def pct(a, b):
    return None if not a or not b else (a / b - 1) * 100


def build(upd, day):
    D = json.load(open("data/stats/fx.json"))
    dates, R = D["dates"], D["rates"]
    last = dates[-1]
    src = D["source"]
    ccy = sorted((c for c in R if last in R[c]), key=lambda c: NAMES.get(c, c))
    os.makedirs(OUT + "/data", exist_ok=True)
    json.dump(D, open(OUT + "/data/stats-fx.json", "w"), separators=(",", ":"))

    def at(c, i):
        return R[c].get(dates[i]) if -len(dates) <= i < 0 else None

    rows, mdrows = [], []
    for c in ccy:
        v = R[c][last]
        ch1, ch7 = pct(v, at(c, -2)), pct(v, at(c, -6))
        s = lambda x: "" if x is None else f"{x:+.2f}%"
        rows.append([f'<a href="/stats/fx/eur-{c.lower()}/">{c}</a>', e(NAMES.get(c, c)), fmt(v), s(ch1), s(ch7)])
        mdrows.append(f"| {c} | {NAMES.get(c, c)} | {fmt(v)} | {s(ch1)} | {s(ch7)} | {BASE_URL}/stats/fx/eur-{c.lower()}/ |")
    hdr = ["Code", "Currency", f"1 EUR = (ECB, {last})", "vs prev. day", "vs 5 days ago"]
    intro = (f"Official euro foreign exchange reference rates published by the European Central Bank for {bs.period_h(last)}: 1 EUR in {len(ccy)} currencies, "
             "with daily change and 90-day history. The ECB publishes them around 16:00 CET on every TARGET working day; we re-fetch them daily.")
    body = (f"<h1>Euro exchange rates today (ECB reference rates)</h1><p>{e(intro)}</p>" + table(hdr, rows, num_cols=(2, 3, 4)) +
            '<p>Machine-readable: <a href="/data/stats-fx.json">/data/stats-fx.json</a> (90 days, all currencies) · Markdown: <a href="/stats/fx/index.md">index.md</a> · '
            f'MCP tool <code>fx_rate</code> on <a href="https://datacensus.org/mcp">datacensus.org/mcp</a>. Source: {e(src)}. Reference rates, not transaction rates; not financial advice.</p>')
    page("/stats/fx/", "Euro exchange rates today (ECB reference rates, 30 currencies)", intro[:300], body, upd)
    bs.write_text("/stats/fx/index.md", bs.md_doc("Euro exchange rates today (ECB reference rates)", intro,
                  ["| Code | Currency | 1 EUR = | vs prev. day | vs 5 days ago | Page |", "|---|---|---|---|---|---|"] + mdrows, BASE_URL + "/stats/fx/", upd))
    for c in ccy:
        ser = [(d, R[c][d]) for d in dates if d in R[c]]
        v = R[c][last]
        vals = [x[1] for x in ser]
        lo, hi = min(vals), max(vals)
        nm = NAMES.get(c, c)
        ch = lambda k: pct(v, at(c, -1 - k))
        facts = [f"1 EUR = {fmt(v)} {c} ({nm}) on {bs.period_h(last)} (ECB reference rate).",
                 f"1 {c} = {1 / v:.6g} EUR."]
        if at(c, -2): facts.append(f"Change vs previous working day: {ch(1):+.2f}%.")
        if at(c, -6): facts.append(f"Change vs 5 working days earlier: {ch(5):+.2f}%.")
        if len(ser) > 20: facts.append(f"Change over the last {len(ser) - 1} working days: {pct(v, ser[0][1]):+.2f}%.")
        facts.append(f"Range over the last {len(ser)} working days: {fmt(lo)} to {fmt(hi)}.")
        cross = ""
        if c != "USD" and "USD" in R and last in R["USD"]:
            cross = f"Implied {c} per US dollar: {R[c][last] / R['USD'][last]:.4g}."
            facts.append(cross)
        ch_svg = bs.chart([(d.split("-", 1)[1] if False else d, x) for d, x in ser[-36:]], f"EUR/{c} last {min(36, len(ser))} working days", "")
        hist = table(["Date", f"1 EUR in {c}"], [[bs.period_h(d), fmt(x)] for d, x in reversed(ser[-30:])], num_cols=(1,))
        title = f"EUR to {c} exchange rate today: 1 euro in {nm}"
        body = (f"<h1>EUR/{c}: 1 euro = {fmt(v)} {e(nm)} ({e(bs.period_h(last))})</h1><ul class=\"facts\">" + "".join(f"<li>{e(f)}</li>" for f in facts) + "</ul>" +
                ch_svg + "<h2>Last 30 working days</h2>" + hist +
                f'<p><a href="/stats/fx/">All euro exchange rates</a> · <a href="/stats/fx/eur-{c.lower()}/index.md">Markdown</a> · <a href="/data/stats-fx.json">JSON</a> · Source: {e(src)}. Reference rates, not transaction rates; not financial advice.</p>')
        page(f"/stats/fx/eur-{c.lower()}/", title, facts[0] + " " + facts[1], body, upd)
        bs.write_text(f"/stats/fx/eur-{c.lower()}/index.md", bs.md_doc(f"EUR/{c} exchange rate", " ".join(facts[:3]),
                      facts[3:] + ["", "| Date | 1 EUR in " + c + " |", "|---|---|"] + [f"| {d} | {fmt(x)} |" for d, x in reversed(ser[-30:])], f"{BASE_URL}/stats/fx/eur-{c.lower()}/", upd))
    return {"currencies": len(ccy), "last": last}
