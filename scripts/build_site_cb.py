"""/stats/central-banks/: current policy rates + official decision calendar (data/stats/cb_rates.json, scripts/fetch_cb_rates.py).
Index + one page per bank (+ .md twins) + /data/stats-central-banks.json."""
import datetime as dt, json, os
from sitelib import *
import build_site_stats as bs

DISCL = "Not financial advice. Dates are taken from each central bank's official published calendar; rates from official data feeds (or BIS where noted)."


def pct(v):
    return "–" if v is None else (f"{v:.3f}".rstrip("0").rstrip(".") + "%")


def bp(x):
    return f"{x:+d} bp" if x else "0 bp"


def days_to(d, today):
    n = (dt.date.fromisoformat(d) - today).days
    return "today" if n == 0 else ("tomorrow" if n == 1 else f"in {n} days")


def build(upd, day):
    D = json.load(open("data/stats/cb_rates.json", encoding="utf-8"))
    B = D["banks"]
    today = dt.date.fromisoformat(day)
    os.makedirs(OUT + "/data", exist_ok=True)
    slim = {"generated": D["generated"], "banks": {c: {k: v for k, v in b.items() if k != "history"} | {"history_last_90d": dict(list(b.get("history", {}).items())[-90:])} for c, b in B.items()}}
    json.dump(slim, open(OUT + "/data/stats-central-banks.json", "w"), ensure_ascii=False, separators=(",", ":"))
    slug = {c: bs.slugify(b["bank"]) for c, b in B.items()}
    order = sorted(B, key=lambda c: (B[c].get("next_meeting") or "9999", B[c]["bank"]))

    def fact(c):
        b = B[c]
        t = f"{b['bank']}: {b.get('rate_label') or b.get('rate_name')} is {pct(b.get('rate'))}"
        if b.get("as_of"): t += f" (as of {bs.period_h(b['as_of'])})"
        lc = b.get("last_change")
        if lc: t += f"; last changed on {bs.period_h(lc['date'])} from {pct(lc['from'])} to {pct(lc['to'])}"
        if b.get("next_meeting"): t += f". Next scheduled decision: {bs.period_h(b['next_meeting'])} ({days_to(b['next_meeting'], today)})"
        return t + "."

    # ---- index
    rows, md = [], []
    week = [c for c in order if B[c].get("next_meeting") and (dt.date.fromisoformat(B[c]["next_meeting"]) - today).days <= 7]
    for c in order:
        b = B[c]
        lc = b.get("last_change")
        nm = b.get("next_meeting")
        rows.append([f'<a href="/stats/central-banks/{slug[c]}/">{e(b["bank"])}</a>', pct(b.get("rate")), bs.period_h(b["as_of"]) if b.get("as_of") else "–",
                     (f"{bs.period_h(lc['date'])} ({bp(round((lc['to'] - lc['from']) * 100))})" if lc else "–"),
                     (f"{bs.period_h(nm)} ({days_to(nm, today)})" if nm else "not published")])
        md.append(f"| {b['bank']} | {pct(b.get('rate'))} | {b.get('as_of') or '–'} | {lc['date'] + ' ' + bp(round((lc['to'] - lc['from']) * 100)) if lc else '–'} | {nm or '–'} | {BASE_URL}/stats/central-banks/{slug[c]}/ |")
    intro = (f"Current policy interest rates of {len(B)} central banks and the dates of their next scheduled rate decisions, "
             "taken from each bank's official calendar. Rates are re-fetched every day (and several times on decision days) from official data feeds; "
             "past decisions are classified as hike / cut / hold from the rate series.")
    wk = ""
    if week:
        wk = "<h2>Decisions in the next 7 days</h2><ul class=\"facts\">" + "".join(
            f"<li><a href=\"/stats/central-banks/{slug[c]}/\">{e(B[c]['bank'])}</a>: {e(bs.period_h(B[c]['next_meeting']))} ({days_to(B[c]['next_meeting'], today)})"
            f"{' at ' + e(B[c]['announcement_time_local']) if B[c].get('announcement_time_local') else ''}; current rate {pct(B[c].get('rate'))}.</li>" for c in week) + "</ul>"
    body = (f"<h1>Central bank interest rate decisions: calendar and current rates</h1><p>{e(intro)}</p>{wk}" +
            table(["Central bank", "Policy rate", "As of", "Last change", "Next decision"], rows, num_cols=(1,)) +
            "<h2>Key facts</h2><ul class=\"facts\">" + "".join(f"<li>{e(fact(c))}</li>" for c in order) + "</ul>" +
            '<p>Machine-readable: <a href="/data/stats-central-banks.json">/data/stats-central-banks.json</a> · Markdown: <a href="/stats/central-banks/index.md">index.md</a> · '
            'MCP tool <code>central_bank_rates</code> on <a href="https://datacensus.org/mcp">datacensus.org/mcp</a> · Monthly history for 59 countries: <a href="/stats/interest-rate/">policy rates by country</a>. '
            f"{e(DISCL)}</p>")
    title = "Central bank rate decisions 2026–2027: calendar and current interest rates (Fed, ECB, BoE, BoJ…)"
    ld = {"@context": "https://schema.org", "@type": "Dataset", "name": "Central bank policy rates and decision calendar", "description": intro,
          "url": BASE_URL + "/stats/central-banks/", "license": "https://creativecommons.org/licenses/by/4.0/", "dateModified": D["generated"],
          "creator": {"@type": "Organization", "name": "datacensus.org"},
          "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": BASE_URL + "/data/stats-central-banks.json"}]}
    page("/stats/central-banks/", title, intro[:300], body, upd, ld)
    bs.write_text("/stats/central-banks/index.md", bs.md_doc("Central bank interest rate decisions: calendar and current rates", intro,
                  ["| Central bank | Policy rate | As of | Last change | Next decision | Page |", "|---|---|---|---|---|---|"] + md + ["", "## Key facts", ""] +
                  [f"- {fact(c)}" for c in order] + ["", DISCL], BASE_URL + "/stats/central-banks/", upd))

    # ---- per bank
    for c in order:
        b = B[c]
        s = slug[c]
        nm = b.get("next_meeting")
        facts = [fact(c)]
        if b.get("announcement_time_local"): facts.append(f"Decisions are announced at {b['announcement_time_local']}.")
        for k, v in (b.get("other_rates") or {}).items():
            facts.append(f"{k.replace('_', ' ').capitalize()}: {pct(v[1])} (as of {bs.period_h(v[0])}).")
        pr = b.get("latest_press_release")
        if pr and pr.get("title"):
            facts.append(f"Latest monetary policy press release{(' (' + bs.period_h(pr['date']) + ')') if pr.get('date') else ''}: “{pr['title']}”.")
        facts.append(f"Rate source: {b.get('source', 'n/a')}" + (f" [{b['feed']}]" if b.get("feed") and b["feed"] != "official" else "") + ".")
        if b.get("notes"): facts.append(f"Note: {b['notes']}")
        past = b.get("decisions") or []
        drows = [[bs.period_h(x["date"]), pct(x.get("before")), pct(x.get("after")), (bp(x["change_bp"]) if "change_bp" in x else "–"), x["outcome"]] for x in reversed(past)]
        up = [m for m in b["meetings"] if m >= day]
        hist = list((b.get("history") or {}).items())
        ch = bs.chart([(d, v) for d, v in hist[-36:]], f"{b['bank']} policy rate, last {min(36, len(hist))} observations", "%") if len(hist) > 2 else ""
        pr_html = (f'<p>Latest press release: <a href="{e(pr["link"])}" rel="nofollow">{e(pr["title"])}</a>{" (" + e(bs.period_h(pr["date"])) + ")" if pr.get("date") else ""}</p>'
                   if pr and pr.get("title") and pr.get("link") else "")
        h1 = f"{b['bank']}: next rate decision {bs.period_h(nm)}" if nm else f"{b['bank']}: policy rate and decisions"
        body = (f'<p class="meta"><a href="/stats/central-banks/">Central bank decisions</a></p><h1>{e(h1)}</h1><ul class="facts">' + "".join(f"<li>{e(f)}</li>" for f in facts) + "</ul>" + pr_html +
                ("<h2>Upcoming scheduled decisions</h2><ul>" + "".join(f"<li>{e(bs.period_h(m))} ({days_to(m, today)})</li>" for m in up) + "</ul>" if up else "") +
                (("<h2>Past decisions (from the rate series)</h2>" + table(["Decision date", "Rate before", "Rate after", "Change", "Outcome"], drows, num_cols=(1, 2, 3))) if drows else "") +
                ch +
                f'<p>Official calendar: <a href="{e(b.get("calendar_url") or "")}">{e(b.get("calendar_url") or "")}</a> · <a href="/stats/central-banks/{s}/index.md">Markdown</a> · '
                f'<a href="/data/stats-central-banks.json">JSON</a> · <a href="/stats/central-banks/">All central banks</a>. {e(DISCL)} '
                "“Outcome” is derived from the official rate series (rate before vs. up to 10 days after the decision, to allow for the effective date).</p>")
        title = (f"{b['bank']} interest rate decision {bs.period_h(nm)}: current rate {pct(b.get('rate'))}, next meeting dates" if nm
                 else f"{b['bank']} interest rate: current {pct(b.get('rate'))}, decisions")
        page(f"/stats/central-banks/{s}/", title, facts[0][:300], body, upd)
        bs.write_text(f"/stats/central-banks/{s}/index.md", bs.md_doc(h1, facts[0], [f"- {f}" for f in facts[1:]] +
                      (["", "## Upcoming scheduled decisions", ""] + [f"- {m}" for m in up] if up else []) +
                      (["", "## Past decisions", "", "| Date | Before | After | Change | Outcome |", "|---|---|---|---|---|"] + [f"| {' | '.join(r)} |" for r in drows] if drows else []) +
                      ["", f"Official calendar: {b.get('calendar_url')}", DISCL], f"{BASE_URL}/stats/central-banks/{s}/", upd))
    return {"banks": len(B)}
