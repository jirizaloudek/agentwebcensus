"""Per-domain pages: /ai-crawlers/site/<domain>/ (top 1,000 ranked domains with a readable robots.txt) and /ai-crawlers/sites/ index."""
import datetime as dt
from sitelib import *

TOP_N = 1000
WORDS = {"F": "Blocked site-wide", "P": "Partially restricted", "A": "Explicitly allowed", "*": "Blocked via blanket * rule"}
NOT_NAMED = "Not named (default rules apply)"

def build(W, domains, upd, day):
    gen = W["generated"]; mon = dt.date.fromisoformat(gen).strftime("%b %Y")
    cat = W["bots_catalog"]
    ai = [b for b in cat if not cat[b].get("comparison_only")]
    N = W["domains_scanned"]
    sel = [d for d in domains["domains"] if d["r"] <= TOP_N and d["rb"] == "ok"]
    cnt = lambda d, c: sum(1 for b in ai if d["b"].get(b) == c)
    joinl = lambda xs: xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]
    scope = f"Tranco list {W.get('tranco_list_id','')}"
    for i, d in enumerate(sel):
        dom, bm = d["d"], d["b"]
        nf, nstar, np_, na = cnt(d, "F"), cnt(d, "*"), cnt(d, "P"), cnt(d, "A")
        named_f = [b for b in ("GPTBot", "ClaudeBot") if bm.get(b) == "F"]
        if nf:
            ans = f"Yes — as of {gen}, {dom}'s robots.txt blocks {nf} of the {len(ai)} AI crawlers we track site-wide" + (f", including {joinl(named_f)}" if named_f else "") + "."
            short = "Yes"
        elif d["s"]:
            ans = f"Yes, indirectly — as of {gen}, {dom}'s robots.txt blocks every crawler, including AI crawlers, with a blanket User-agent: * / Disallow: / rule; none of the {len(ai)} AI crawlers we track is named."
            short = "Yes (blanket rule)"
        elif np_:
            ans = f"Partly — as of {gen}, {dom}'s robots.txt does not block any of the {len(ai)} AI crawlers we track site-wide, but restricts {np_} of them from parts of the site."
            short = "Partly"
        else:
            ans = f"No — as of {gen}, {dom}'s robots.txt does not block any of the {len(ai)} AI crawlers we track" + (f" (it explicitly allows {na})." if na else " (none is named in it).")
            short = "No"
        if nf and d["s"]:
            ans += " It also has a blanket rule blocking all other crawlers."
        rows = []
        for b in cat:
            c = bm.get(b)
            rows.append([b, cat[b]["operator"], cat[b]["purpose"] + (" (comparison, not AI)" if b not in ai else ""), WORDS.get(c, NOT_NAMED)])
        cs = d.get("cs")
        cs_txt = ", ".join(f"{k}={v}" for k, v in sorted(cs.items())) if cs else "none found"
        llms = "present (format check)" if d["l"] else "not found"
        x = d.get("x")
        exc = (f"<h2>Relevant robots.txt lines</h2><pre>{e(x)}</pre><p class=\"meta\">Only groups naming a tracked AI crawler, at most 40 lines, from the scan of {gen}.</p>" if x
               else "<h2>Relevant robots.txt lines</h2><p>No group in this robots.txt names an AI crawler we track.</p>")
        prev = sel[i - 1] if i else None; nxt = sel[i + 1] if i + 1 < len(sel) else None
        nav = " · ".join(x_ for x_ in [f'<a href="/ai-crawlers/site/{e(prev["d"])}/">← #{prev["r"]} {e(prev["d"])}</a>' if prev else "",
                                       f'<a href="/ai-crawlers/site/{e(nxt["d"])}/">#{nxt["r"]} {e(nxt["d"])} →</a>' if nxt else "",
                                       '<a href="/ai-crawlers/sites/">all sites</a>', '<a href="/ai-crawlers/">AI crawler statistics</a>'] if x_)
        CITE = f"Agent Web Census, “Does {dom} block AI crawlers?”, {BASE_URL}/ai-crawlers/site/{dom}/, robots.txt scan of {gen} ({scope})."
        body = f"""<h1>Does {e(dom)} block AI crawlers?</h1>
<p><b>{e(ans)}</b></p>
{kpis([(f"#{d['r']}", "Tranco rank"), (nf, f"of {len(ai)} AI crawlers blocked site-wide"), (np_ + na, "partially restricted or explicitly allowed"), ("yes" if d["l"] else "no", "llms.txt present (format check)")])}
<h2>Status of each crawler</h2>{table(['Crawler','Operator','Purpose','Status in robots.txt'], rows)}
<p class="meta">“Not named” means no group in the robots.txt names the crawler, so the <code>User-agent: *</code> rules apply{' (here the * group blocks the whole site)' if d['s'] else ''}.</p>
<h2>Other signals</h2><ul class="facts"><li>llms.txt: {llms}.</li><li>Content-Signal directive (Cloudflare): {e(cs_txt)}.</li><li>Blanket block of all bots (<code>User-agent: *</code> / <code>Disallow: /</code>): {'yes' if d['s'] else 'no'}.</li><li>AI crawlers named in robots.txt: {d['n']} of {len(ai)}.</li>
<li>Live file: <a href="https://{e(dom)}/robots.txt" rel="nofollow noopener">https://{e(dom)}/robots.txt</a></li></ul>
{exc}
<p class="meta"><b>Note:</b> robots.txt is a voluntary standard (RFC 9309); it does not technically stop any crawler, and a site may also block bots by other means. The file may have changed since the scan on {gen}; check the live file above. See the <a href="/about/#methodology">methodology</a> for how statuses are derived.</p>
{cite_box(e(CITE))}
<p>{nav}</p>"""
        page(f"/ai-crawlers/site/{dom}/", f"Does {dom} block AI crawlers? GPTBot, ClaudeBot & more ({mon})",
             f"{short}: {dom} (Tranco rank {d['r']}) blocks {nf} of {len(ai)} tracked AI crawlers site-wide in robots.txt (scan of {gen}). GPTBot: {WORDS.get(bm.get('GPTBot'), 'not named').lower()}; ClaudeBot: {WORDS.get(bm.get('ClaudeBot'), 'not named').lower()}.",
             body, gen)

    code = lambda d, b: {"F": "blocked", "P": "partial", "A": "allowed", "*": "blocked (* rule)"}.get(d["b"].get(b), "not named")
    trs = "".join(f'<tr><td class="n">{d["r"]}</td><td><a href="/ai-crawlers/site/{e(d["d"])}/">{e(d["d"])}</a></td><td class="n">{cnt(d, "F")}</td>'
                  f'<td>{code(d, "GPTBot")}</td><td>{code(d, "ClaudeBot")}</td><td>{"yes" if d["l"] else "no"}</td></tr>' for d in sel)
    js = """<script>var q=document.getElementById('q');if(q){q.oninput=function(){var v=q.value.toLowerCase().trim();document.querySelectorAll('#t tbody tr').forEach(function(r){r.style.display=r.cells[1].textContent.indexOf(v)<0?'none':''})}}</script>"""
    body = f"""<h1>Which top websites block AI crawlers? ({mon})</h1>
<p>robots.txt policies of the {fmt(len(sel))} highest-ranked of the top {fmt(N)} websites ({e(scope)}) that serve a readable robots.txt, scan of {gen}. Click a domain for the full per-crawler answer. Domains whose robots.txt could not be read are not listed.</p>
<p><label>Filter by domain: <input id="q" type="search" placeholder="e.g. nytimes" autocomplete="off"></label></p>
<table id="t"><thead><tr><th class="n">Rank</th><th>Domain</th><th class="n">AI bots blocked</th><th>GPTBot</th><th>ClaudeBot</th><th>llms.txt</th></tr></thead><tbody>{trs}</tbody></table>{js}
<p class="meta">“AI bots blocked” = number of the {len(ai)} AI crawlers we track that are blocked site-wide by name. “blocked (* rule)” = not named, but a blanket <code>User-agent: *</code> rule blocks everything. robots.txt is voluntary and may have changed since the scan.</p>
{cite_box(e(f'Agent Web Census, “Which top websites block AI crawlers?”, {BASE_URL}/ai-crawlers/sites/, scan of {gen}.'))}
<p><a href="/ai-crawlers/">← AI crawler statistics</a></p>"""
    page("/ai-crawlers/sites/", f"Which top websites block AI crawlers? Searchable list of {fmt(len(sel))} sites ({mon})",
         f"Searchable list of the {fmt(len(sel))} most popular websites with a robots.txt and whether each blocks GPTBot, ClaudeBot and other AI crawlers (scan of {gen}).", body, gen)
    return len(sel)
