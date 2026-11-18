"""AI-crawler policy pages: /ai-crawlers/, /ai-crawlers/<bot>/, /ai-crawlers/tld/<tld>/, /llms-txt-adoption/."""
import re
from sitelib import *

slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

def build(W, upd, day):
    O, cat = W["overall"], W["bots_catalog"]
    N, R = W["domains_scanned"], W["robots_reachable"]
    ai = [b for b in cat if not cat[b].get("comparison_only")]
    bots = O["bots"]
    rank = sorted(cat, key=lambda b: -bots[b]["pct_fully_of_reachable"])
    any1 = O["blocking_at_least_one_ai_bot_fully"]; all4 = O["blocking_all_of_GPTBot_ClaudeBot_Google-Extended_CCBot"]
    L = W["llms_txt"]["overall"]; CS = W.get("content_signal", {})
    scope = f"the top {fmt(N)} websites (Tranco list {W.get('tranco_list_id','')})"
    facts = [
      f"As of {day}, {any1['pct_of_reachable']}% of {scope} with a robots.txt fully block at least one AI crawler.",
      f"GPTBot (OpenAI) is fully blocked by {bots['GPTBot']['pct_fully_of_reachable']}% and ClaudeBot (Anthropic) by {bots['ClaudeBot']['pct_fully_of_reachable']}% of top-{fmt(N)} sites with a robots.txt; Googlebot by only {bots['Googlebot']['pct_fully_of_reachable']}%.",
      f"{all4['pct_of_reachable']}% of top-{fmt(N)} sites with a robots.txt block all four of GPTBot, ClaudeBot, Google-Extended and CCBot.",
      f"{L['pct_valid']}% of the top {fmt(N)} websites publish a valid /llms.txt file.",
      f"The most-blocked AI crawler among the top {fmt(N)} sites is {rank[0] if rank[0]!='Googlebot' else rank[1]} ({bots[rank[0]]['pct_fully_of_reachable']}% fully blocked).",
    ]
    if CS: facts.append(f"{CS.get('pct_of_reachable')}% of top-{fmt(N)} robots.txt files contain a Cloudflare Content-Signal directive.")
    W["headline_facts"] = facts
    CITE = f"Agent Web Census, “AI crawler blocking statistics”, {BASE_URL}/ai-crawlers/, scan of {scope} on {W['generated']}."
    rows = [[f'<a href="/ai-crawlers/{slug(b)}/">{e(b)}</a>', cat[b]["operator"], cat[b]["purpose"], f"{bots[b]['pct_fully_of_reachable']}%",
             f"{bots[b]['pct_partially_of_reachable']}%", f"{bots[b]['pct_allowed_explicitly_of_reachable']}%"] for b in rank]
    buckets = W["by_rank_bucket"]
    bk = [[k, v["scanned"], f"{v['blocking_at_least_one_ai_bot_fully']['pct_of_reachable']}%", f"{v['bots']['GPTBot']['pct_fully_of_reachable']}%",
           f"{v['bots']['ClaudeBot']['pct_fully_of_reachable']}%"] for k, v in buckets.items()]
    tlds = [(t, v) for t, v in W["by_tld"].items() if v["robots_reachable"] >= 15]
    body = f"""<h1>AI crawler blocking statistics ({day[:7]})</h1>
<p class="meta">Which AI bots do the world’s most popular websites block in robots.txt? Measured directly on {scope}. Re-scanned weekly.</p>
{kpis([(f"{any1['pct_of_reachable']}%","block ≥1 AI crawler fully"),(f"{bots['GPTBot']['pct_fully_of_reachable']}%","block GPTBot"),(f"{bots['ClaudeBot']['pct_fully_of_reachable']}%","block ClaudeBot"),(f"{L['pct_valid']}%","have a valid llms.txt"),(N,"domains scanned"),(R,"with a readable robots.txt")])}
<h2>Key facts</h2><ul class="facts">{''.join(f'<li>{e(f)}</li>' for f in facts)}</ul>{cite_box(e(CITE))}
<h2>Share of sites fully blocking each crawler</h2>{hbar([(b, bots[b]['pct_fully_of_reachable']) for b in rank], 'Percent of sites fully blocking each crawler', '%')}
<h2>All crawlers</h2>{table(['Crawler','Operator','Purpose','Fully blocked','Partially','Explicitly allowed'], rows)}
<p class="meta">Percentages are of the {fmt(R)} domains that returned a readable robots.txt. Click a crawler for details.</p>
<h2>By popularity rank</h2>{table(['Bucket','Domains','Block ≥1 AI bot','GPTBot','ClaudeBot'], bk, (1,))}
{('<h2>By top-level domain</h2>' + table(['TLD','Readable robots.txt','Block ≥1 AI bot','GPTBot','ClaudeBot'], [[f'<a href="/ai-crawlers/tld/{slug(t)}/">.{e(t)}</a>', v['robots_reachable'], f"{v['blocking_at_least_one_ai_bot_fully']['pct_of_reachable']}%", f"{v['bots']['GPTBot']['pct_fully_of_reachable']}%", f"{v['bots']['ClaudeBot']['pct_fully_of_reachable']}%"] for t, v in tlds], (1,))) if tlds else ''}
<h2>Other signals</h2><ul><li>{O['star_blocks_everything']['pct_of_reachable']}% of robots.txt files block <em>all</em> bots via <code>User-agent: *</code> / <code>Disallow: /</code>.</li>
<li>A robots.txt names on average {O['mean_ai_bots_named_per_robots_txt']} of the AI crawlers we track ({O['mean_ai_bots_named_per_robots_txt_among_those_naming_any']} among files that name any).</li>
<li><a href="/llms-txt-adoption/">llms.txt adoption: {L['pct_valid']}%</a></li></ul>
<h2>Method</h2><p class="meta">{e(W['methodology'])}</p><p>Data: <a href="/data/web-latest.json">web-latest.json</a> · <a href="/data/web-history.csv">web-history.csv</a></p>"""
    page("/ai-crawlers/", f"AI Crawler Blocking Statistics {day[:4]}: who blocks GPTBot, ClaudeBot & co. (top {fmt(N)} sites)",
         f"{any1['pct_of_reachable']}% of top websites block at least one AI crawler. Live, measured stats for GPTBot, ClaudeBot, Google-Extended, PerplexityBot, CCBot and more.", body, upd,
         {"@context": "https://schema.org", "@type": "Dataset", "name": "AI crawler robots.txt policies of top websites", "url": BASE_URL + "/ai-crawlers/",
          "dateModified": upd, "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": SITE_NAME},
          "distribution": [{"@type": "DataDownload", "encodingFormat": "json", "contentUrl": BASE_URL + "/data/web-latest.json"}]})

    for b in cat:
        s = bots[b]; c = cat[b]
        f = [f"As of {W['generated']}, {s['pct_fully_of_reachable']}% of {scope} with a readable robots.txt fully block {b} ({c['operator']}, {c['purpose']} crawler).",
             f"A further {s['pct_partially_of_reachable']}% restrict {b} partially, and {s['pct_allowed_explicitly_of_reachable']}% explicitly allow it.",
             f"{fmt(s['not_mentioned'])} sites do not mention {b}; of those, {fmt(s['not_mentioned_but_star_blocks_all'])} block all bots via the * group."]
        bb = [[k, f"{v['bots'][b]['pct_fully_of_reachable']}%", f"{v['bots'][b]['pct_partially_of_reachable']}%"] for k, v in buckets.items()]
        tb = [[f".{t}", f"{v['bots'][b]['pct_fully_of_reachable']}%"] for t, v in tlds]
        pos = rank.index(b) + 1
        body = f"""<h1>How many websites block {e(b)}? ({day[:7]})</h1>
{kpis([(f"{s['pct_fully_of_reachable']}%", "fully blocked"), (f"{s['pct_partially_of_reachable']}%", "partially restricted"), (f"{s['pct_allowed_explicitly_of_reachable']}%", "explicitly allowed"), (f"#{pos}/{len(rank)}", "most-blocked rank")])}
<p><b>{e(b)}</b> is operated by <b>{e(c['operator'])}</b>; purpose: {e(c['purpose'])}.</p>
<h2>Key facts</h2><ul class="facts">{''.join(f'<li>{e(x)}</li>' for x in f)}</ul>
{cite_box(e(f'Agent Web Census, “How many websites block {b}?”, {BASE_URL}/ai-crawlers/{slug(b)}/, scan of {scope} on {W["generated"]}.'))}
<h2>By popularity rank</h2>{table(['Bucket','Fully blocked','Partially'], bb)}
{('<h2>By TLD</h2>' + table(['TLD','Fully blocked'], tb)) if tb else ''}
<h2>How to block or allow {e(b)}</h2><pre><code># block
User-agent: {e(b)}
Disallow: /

# allow
User-agent: {e(b)}
Allow: /</code></pre><p class="meta">robots.txt is a voluntary standard (RFC 9309); compliance depends on the crawler operator.</p>
<p><a href="/ai-crawlers/">← all AI crawlers</a></p>"""
        page(f"/ai-crawlers/{slug(b)}/", f"How many websites block {b}? {s['pct_fully_of_reachable']}% of top sites ({day[:7]})",
             f"Measured: {s['pct_fully_of_reachable']}% of the top {fmt(N)} websites fully block {b} ({c['operator']}) in robots.txt. Updated weekly.", body, upd)

    for t, v in tlds:
        rk = sorted(ai, key=lambda b: -v["bots"][b]["pct_fully_of_reachable"])
        body = f"""<h1>AI crawler blocking on .{e(t)} websites ({day[:7]})</h1>
<p>Among the top {fmt(N)} websites, {fmt(v['scanned'])} are .{e(t)} domains and {fmt(v['robots_reachable'])} have a readable robots.txt. {v['blocking_at_least_one_ai_bot_fully']['pct_of_reachable']}% of those fully block at least one AI crawler.</p>
{hbar([(b, v['bots'][b]['pct_fully_of_reachable']) for b in rk[:15]], f'AI crawlers blocked by .{t} sites', '%')}
<p class="meta">Small samples are noisy; see the sample size above.</p><p><a href="/ai-crawlers/">← all AI crawlers</a></p>"""
        page(f"/ai-crawlers/tld/{slug(t)}/", f"AI crawler blocking on .{t} websites ({day[:7]})", f".{t} sites: {v['blocking_at_least_one_ai_bot_fully']['pct_of_reachable']}% block at least one AI crawler.", body, upd)

    lb = W["llms_txt"]["by_rank_bucket"]
    body = f"""<h1>llms.txt adoption statistics ({day[:7]})</h1>
{kpis([(f"{L['pct_valid']}%", f"of top {fmt(N)} sites have a valid llms.txt"), (L['valid'], 'sites with valid llms.txt'), (f"{L['pct_http200']}%", 'return HTTP 200 on /llms.txt (incl. soft-404s)')])}
<ul class="facts"><li>{e(facts[3])}</li></ul>{cite_box(e(f'Agent Web Census, “llms.txt adoption statistics”, {BASE_URL}/llms-txt-adoption/, scan of {scope} on {W["generated"]}.'))}
{table(['Bucket','Scanned','Valid llms.txt'], [[k, x['scanned'], f"{x['pct_valid']}%"] for k, x in lb.items()], (1,))}
<p class="meta">“Valid” = HTTP 200, text/plain or text/markdown, not HTML, starts with a Markdown heading. Many sites answer 200 with an HTML page for any path; those are not counted.</p>"""
    page("/llms-txt-adoption/", f"llms.txt adoption: {L['pct_valid']}% of top {fmt(N)} websites ({day[:7]})", f"How many websites have an llms.txt? Measured on the top {fmt(N)} sites: {L['pct_valid']}%.", body, upd)
