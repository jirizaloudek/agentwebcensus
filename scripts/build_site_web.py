"""AI-crawler policy pages: /ai-crawlers/, /ai-crawlers/<bot>/, /ai-crawlers/tld/<tld>/, /llms-txt-adoption/."""
import re, datetime as dt
from sitelib import *

slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
MIN_N, SMALL_N = 30, 100  # TLD pages/rows only for n >= 30; "small sample" note when n < 100

def build(W, upd, day):
    gen = W["generated"]; mon = dt.date.fromisoformat(gen).strftime("%b %Y")  # scan date drives all crawler pages
    O, cat = W["overall"], W["bots_catalog"]
    N, R = W["domains_scanned"], W["robots_reachable"]
    for b in cat:  # effective block = named site-wide block + blanket "User-agent: * / Disallow: /"
        x = O["bots"][b]; k = x["blocked_fully"] + x["not_mentioned_but_star_blocks_all"]
        x["pct_effective_of_reachable"] = round(100 * k / R, 1) if R else 0
        x["pct_effective_of_all_scanned"] = round(100 * k / N, 1) if N else 0
    ai = [b for b in cat if not cat[b].get("comparison_only")]
    bots = O["bots"]
    rank = sorted(cat, key=lambda b: -bots[b]["pct_fully_of_reachable"])
    any1 = O["blocking_at_least_one_ai_bot_fully"]; all4 = O["blocking_all_of_GPTBot_ClaudeBot_Google-Extended_CCBot"]
    L = W["llms_txt"]["overall"]; CS = W.get("content_signal", {})
    scope = f"the top {fmt(N)} websites (Tranco list {W.get('tranco_list_id','')})"
    den = f"of the {fmt(R)} top-{fmt(N)} sites with a readable robots.txt"
    allp = lambda p: f"{p}% of all {fmt(N)} scanned"
    top_ai = next(b for b in rank if b != "Googlebot")
    facts = [
      f"As of {gen}, {any1['pct_of_reachable']}% {den} ({allp(any1['pct_of_all_scanned'])}) block at least one AI crawler by name across the whole site.",
      f"As of {gen}, {bots['GPTBot']['pct_fully_of_reachable']}% {den} ({allp(bots['GPTBot']['pct_fully_of_all_scanned'])}) block OpenAI’s GPTBot site-wide and {bots['ClaudeBot']['pct_fully_of_reachable']}% ({allp(bots['ClaudeBot']['pct_fully_of_all_scanned'])}) block Anthropic’s ClaudeBot, versus {bots['Googlebot']['pct_fully_of_reachable']}% for Googlebot (search, not an AI-training crawler; shown for comparison).",
      f"As of {gen}, {all4['pct_of_reachable']}% {den} ({allp(all4['pct_of_all_scanned'])}) block all four of GPTBot, ClaudeBot, Google-Extended and CCBot site-wide.",
      f"As of {gen}, {L['pct_valid']}% of all {fmt(N)} scanned top sites have an llms.txt present (format check: HTTP 200, text/plain or text/markdown, starts with a Markdown heading, not HTML; requested on the host that served robots.txt).",
      f"As of {gen}, the most-blocked AI crawler {den} is {top_ai} ({bots[top_ai]['pct_fully_of_reachable']}% block it site-wide).",
    ]
    if CS: facts.append(f"As of {gen}, {CS.get('pct_of_reachable')}% {den} ({allp(CS.get('pct_of_all_scanned'))}) contain a Cloudflare Content-Signal directive.")
    W["headline_facts"] = facts
    CITE = f"Agent Web Census, “AI crawler blocking statistics”, {BASE_URL}/ai-crawlers/, scan of {scope} on {gen}."
    DEFS = lambda extra="": f"""<div class="cite"><b>Definitions</b><ul><li><b>Blocked site-wide (by name)</b>: a robots.txt group naming the bot has <code>Disallow: /</code> without <code>Allow: /</code> (narrow Allow exceptions are tolerated).</li>
<li><b>Effectively blocked</b>: blocked site-wide as above, or a blanket <code>User-agent: *</code> group with <code>Disallow: /</code>.</li>
<li><b>Partially restricted</b>: a group naming the bot has other Disallow rules.</li>
<li>Purpose labels (training, search, user-triggered) follow each operator’s public documentation.</li>{extra}</ul></div>"""
    GB = "<li>Googlebot (search, not an AI-training crawler) is shown for comparison.</li>"
    rows = [[f'<a href="/ai-crawlers/{slug(b)}/">{e(b)}</a>', cat[b]["operator"], cat[b]["purpose"], f"{bots[b]['pct_fully_of_reachable']}%", f"{bots[b]['pct_effective_of_reachable']}%",
             f"{bots[b]['pct_partially_of_reachable']}%", f"{bots[b]['pct_allowed_explicitly_of_reachable']}%"] for b in rank]
    buckets = W["by_rank_bucket"]
    bk = [[k, v["scanned"], v["robots_reachable"], f"{v['blocking_at_least_one_ai_bot_fully']['pct_of_reachable']}%", f"{v['bots']['GPTBot']['pct_fully_of_reachable']}%",
           f"{v['bots']['ClaudeBot']['pct_fully_of_reachable']}%"] for k, v in buckets.items()]
    note = lambda n: f"small sample (n={n}), treat with caution" if n < SMALL_N else ""
    tlds = [(t, v) for t, v in W["by_tld"].items() if v["robots_reachable"] >= MIN_N]
    tld_tbl = ('<h2>By top-level domain</h2>' + table(['TLD','n (readable robots.txt)','Block ≥1 AI bot','GPTBot','ClaudeBot','Note'], [[f'<a href="/ai-crawlers/tld/{slug(t)}/">.{e(t)}</a>', v['robots_reachable'], f"{v['blocking_at_least_one_ai_bot_fully']['pct_of_reachable']}%", f"{v['bots']['GPTBot']['pct_fully_of_reachable']}%", f"{v['bots']['ClaudeBot']['pct_fully_of_reachable']}%", note(v['robots_reachable'])] for t, v in tlds], (1,))
               + f'<p class="meta">n = domains of that TLD with a readable robots.txt; percentages are of n. TLDs with n &lt; {MIN_N} are omitted.</p>') if tlds else ''
    body = f"""<h1>AI crawler blocking statistics ({mon})</h1>
<p class="meta">Which AI bots do the world’s most popular websites block in robots.txt? Measured directly on {scope}; scan of {gen}. The crawler scan is repeated weekly (the MCP statistics are updated daily).</p>
{kpis([(f"{any1['pct_of_reachable']}%","of sites with a readable robots.txt block ≥1 AI crawler by name"),(f"{bots['GPTBot']['pct_fully_of_reachable']}%","of sites with a readable robots.txt block GPTBot"),(f"{bots['ClaudeBot']['pct_fully_of_reachable']}%","of sites with a readable robots.txt block ClaudeBot"),(f"{L['pct_valid']}%",f"of all {fmt(N)} scanned have llms.txt present (format check)"),(N,"domains scanned"),(R,"with a readable robots.txt")])}
<h2>Key facts</h2><ul class="facts">{''.join(f'<li>{e(f)}</li>' for f in facts)}</ul>{cite_box(e(CITE))}
{DEFS(GB)}
<h2>Share of sites blocking each crawler by name (site-wide)</h2>{hbar([(b, bots[b]['pct_fully_of_reachable']) for b in rank], f'Percent of the {fmt(R)} sites with a readable robots.txt fully blocking each crawler', '%')}
<h2>All crawlers</h2>{table(['Crawler','Operator','Purpose','Blocked by name (site-wide)','Effectively blocked (incl. * rule)','Partially','Explicitly allowed'], rows)}
<p class="meta">Percentages are of the {fmt(R)} of {fmt(N)} scanned domains that returned a readable robots.txt. Click a crawler for details.</p>
<h2>By popularity rank</h2>{table(['Bucket','Domains scanned','Readable robots.txt','Block ≥1 AI bot','GPTBot','ClaudeBot'], bk, (1,2))}
<p class="meta">Percentages are of the readable-robots.txt count in the same row; buckets are cumulative (top1k includes top100).</p>
{tld_tbl}
<h2>Other signals</h2><ul><li>{O['star_blocks_everything']['pct_of_reachable']}% {den} block <em>all</em> bots via <code>User-agent: *</code> / <code>Disallow: /</code>.</li>
<li>A robots.txt names on average {O['mean_ai_bots_named_per_robots_txt']} of the AI crawlers we track ({O['mean_ai_bots_named_per_robots_txt_among_those_naming_any']} among files that name any).</li>
<li><a href="/llms-txt-adoption/">llms.txt present (format check): {L['pct_valid']}% of all {fmt(N)} scanned</a></li></ul>
<h2>Method</h2><p class="meta">{e(W['methodology'])}</p><p>Data: <a href="/data/web-latest.json">web-latest.json</a> · <a href="/data/web-history.csv">web-history.csv</a></p>"""
    page("/ai-crawlers/", f"AI Crawler Blocking Statistics ({mon}): who blocks GPTBot, ClaudeBot & co. (top-{fmt(N)} sites with a robots.txt)",
         f"{any1['pct_of_reachable']}% {den} block at least one AI crawler by name site-wide ({allp(any1['pct_of_all_scanned'])}). Scan of {gen}, repeated weekly.", body, gen,
         {"@context": "https://schema.org", "@type": "Dataset", "name": "AI crawler robots.txt policies of top websites", "url": BASE_URL + "/ai-crawlers/",
          "dateModified": gen, "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": SITE_NAME},
          "distribution": [{"@type": "DataDownload", "encodingFormat": "json", "contentUrl": BASE_URL + "/data/web-latest.json"}]})

    for b in cat:
        s = bots[b]; c = cat[b]
        f = [f"As of {gen}, {s['pct_fully_of_reachable']}% {den} ({allp(s['pct_fully_of_all_scanned'])}) block {b} by name across the whole site ({c['operator']}, {c['purpose']} crawler).",
             f"Counting sites that block all bots with a blanket User-agent: * rule, {s['pct_effective_of_reachable']}% {den} ({allp(s['pct_effective_of_all_scanned'])}) effectively block {b}.",
             f"A further {s['pct_partially_of_reachable']}% {den} restrict {b} partially, and {s['pct_allowed_explicitly_of_reachable']}% explicitly allow it.",
             f"{fmt(s['not_mentioned'])} of the {fmt(R)} sites with a readable robots.txt do not mention {b}; of those, {fmt(s['not_mentioned_but_star_blocks_all'])} block all bots via the * group."]
        bb = [[k, v["robots_reachable"], f"{v['bots'][b]['pct_fully_of_reachable']}%", f"{v['bots'][b]['pct_partially_of_reachable']}%"] for k, v in buckets.items()]
        tb = [[f".{t}", v["robots_reachable"], f"{v['bots'][b]['pct_fully_of_reachable']}%", note(v["robots_reachable"])] for t, v in tlds]
        pos = rank.index(b) + 1
        body = f"""<h1>How many websites block {e(b)}? ({mon})</h1>
{kpis([(f"{s['pct_fully_of_reachable']}%", "of sites with a readable robots.txt block it by name, site-wide"), (f"{s['pct_effective_of_reachable']}%", "effectively blocked (incl. * rule)"), (f"{s['pct_partially_of_reachable']}%", "partially restricted"), (f"{s['pct_allowed_explicitly_of_reachable']}%", "explicitly allowed"), (f"#{pos}/{len(rank)}", "most-blocked rank")])}
<p><b>{e(b)}</b> is operated by <b>{e(c['operator'])}</b>; purpose: {e(c['purpose'])}. Scan of {scope} on {gen}; repeated weekly.</p>
<h2>Key facts</h2><ul class="facts">{''.join(f'<li>{e(x)}</li>' for x in f)}</ul>
{cite_box(e(f'Agent Web Census, “How many websites block {b}?”, {BASE_URL}/ai-crawlers/{slug(b)}/, scan of {scope} on {gen}.'))}
{DEFS(GB if b == 'Googlebot' else '')}
<h2>By popularity rank</h2>{table(['Bucket','n (readable robots.txt)','Fully blocked','Partially'], bb, (1,))}
{('<h2>By TLD</h2>' + table(['TLD','n (readable robots.txt)','Fully blocked','Note'], tb, (1,)) + f'<p class="meta">n = domains of that TLD with a readable robots.txt; percentages are of n. TLDs with n &lt; {MIN_N} are omitted.</p>') if tb else ''}
<h2>How to block or allow {e(b)}</h2><pre><code># block
User-agent: {e(b)}
Disallow: /

# allow
User-agent: {e(b)}
Allow: /</code></pre><p class="meta">robots.txt is a voluntary standard (RFC 9309); compliance depends on the crawler operator.</p>
<p><a href="/ai-crawlers/">← all AI crawlers</a></p>"""
        page(f"/ai-crawlers/{slug(b)}/", f"How many websites block {b}? {s['pct_fully_of_reachable']}% of top sites with a robots.txt ({mon})",
             f"Measured {gen}: {s['pct_fully_of_reachable']}% {den} ({allp(s['pct_fully_of_all_scanned'])}) block {b} by name across the whole site ({c['operator']}). Scan repeated weekly.", body, gen)

    for t, v in tlds:
        rk = sorted(ai, key=lambda b: -v["bots"][b]["pct_fully_of_reachable"]); n = v["robots_reachable"]
        body = f"""<h1>AI crawler blocking on .{e(t)} websites ({mon})</h1>
<p>Among the top {fmt(N)} websites (scan of {gen}), {fmt(v['scanned'])} are .{e(t)} domains and {fmt(n)} (n) have a readable robots.txt. {v['blocking_at_least_one_ai_bot_fully']['pct_of_reachable']}% of those {fmt(n)} block at least one AI crawler by name across the whole site.</p>
{f'<p class="meta"><b>Note: {note(n)}.</b></p>' if n < SMALL_N else ''}
{hbar([(b, v['bots'][b]['pct_fully_of_reachable']) for b in rk[:15]], f'AI crawlers blocked by .{t} sites with a readable robots.txt (n={n})', '%')}
<p class="meta">Percentages are of n = {fmt(n)} .{e(t)} sites with a readable robots.txt. Small samples are noisy.</p>{DEFS()}<p><a href="/ai-crawlers/">← all AI crawlers</a></p>"""
        page(f"/ai-crawlers/tld/{slug(t)}/", f"AI crawler blocking on .{t} websites: {v['blocking_at_least_one_ai_bot_fully']['pct_of_reachable']}% of n={n} with a robots.txt ({mon})",
             f".{t} sites: {v['blocking_at_least_one_ai_bot_fully']['pct_of_reachable']}% of the {n} top-{fmt(N)} .{t} sites with a readable robots.txt block at least one AI crawler (scan of {gen})." + (f" {note(n).capitalize()}." if n < SMALL_N else ""), body, gen)

    lb = W["llms_txt"]["by_rank_bucket"]
    body = f"""<h1>llms.txt adoption statistics ({mon})</h1>
{kpis([(f"{L['pct_valid']}%", f"of all {fmt(N)} scanned top sites have llms.txt present (format check)"), (L['valid'], 'sites with llms.txt present (format check)'), (f"{L['pct_http200']}%", 'return HTTP 200 on /llms.txt (incl. soft-404s)')])}
<ul class="facts"><li>{e(facts[3])}</li></ul>{cite_box(e(f'Agent Web Census, “llms.txt adoption statistics”, {BASE_URL}/llms-txt-adoption/, scan of {scope} on {gen}.'))}
{table(['Bucket','Scanned','llms.txt present (format check)'], [[k, x['scanned'], f"{x['pct_valid']}%"] for k, x in lb.items()], (1,))}
<p class="meta">“llms.txt present (format check)” = <code>/llms.txt</code>, requested on the host that served robots.txt, returned HTTP 200 with content-type text/plain or text/markdown, a body that is not HTML and starts with a Markdown heading (<code>#</code>). Content quality is not assessed. Many sites answer 200 with an HTML page for any path; those are not counted. The denominator is all scanned sites, not only those with a readable robots.txt. Scan repeated weekly.</p>"""
    page("/llms-txt-adoption/", f"llms.txt present (format check): {L['pct_valid']}% of the top {fmt(N)} websites ({mon})", f"How many websites have an llms.txt? Scan of {gen}: {L['pct_valid']}% of all {fmt(N)} top sites scanned have llms.txt present (format check).", body, gen)
