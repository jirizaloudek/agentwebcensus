#!/usr/bin/env python3
"""Generate the static site into site/ from data/mcp/*.json and data/web/*.json."""
import json, os, shutil, collections, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from sitelib import *
import sitelib

if os.path.exists(OUT): shutil.rmtree(OUT)
os.makedirs(OUT + "/data", exist_ok=True)
M = json.load(open("data/mcp/latest.json"))
SV = json.load(open("data/mcp/servers.json"))
W = json.load(open("data/web/latest.json")) if os.path.exists("data/web/latest.json") else None
upd = M["generated_at"]; day = upd[:10]
T, G, D, Q = M["totals"], M["growth"], M["deployment"], M["metadata_quality"]
for f in ["data/mcp/latest.json", "data/mcp/history.csv"]:
    shutil.copy(f, f"{OUT}/data/mcp-" + os.path.basename(f))
# servers list: paginated shards (Cloudflare Pages has a 25 MiB/file limit)
PAGE_SZ = 5000
os.makedirs(f"{OUT}/data/mcp-servers", exist_ok=True)
compact = [{k: v for k, v in s.items() if v not in ("", [], None)} for s in SV]
npages = (len(compact) + PAGE_SZ - 1) // PAGE_SZ
for i in range(npages):
    json.dump({"page": i + 1, "pages": npages, "total": len(compact), "sorted_by": "updated desc",
               "next": f"{BASE_URL}/data/mcp-servers/{i+2}.json" if i + 1 < npages else None,
               "servers": compact[i*PAGE_SZ:(i+1)*PAGE_SZ]}, open(f"{OUT}/data/mcp-servers/{i+1}.json", "w"), separators=(",", ":"))
if W:
    for f in ["data/web/latest.json", "data/web/history.csv"]:
        if os.path.exists(f): shutil.copy(f, f"{OUT}/data/web-" + os.path.basename(f))
slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
CITE = f'Agent Web Census, “MCP Registry statistics”, {BASE_URL}/mcp/, data retrieved {day} from the official MCP Registry.'

def dataset_ld(name, desc, path, files):
    return {"@context": "https://schema.org", "@type": "Dataset", "name": name, "description": desc,
            "url": BASE_URL + path, "dateModified": upd, "license": "https://creativecommons.org/licenses/by/4.0/",
            "creator": {"@type": "Organization", "name": SITE_NAME},
            "isBasedOn": "https://registry.modelcontextprotocol.io/",
            "distribution": [{"@type": "DataDownload", "encodingFormat": f.split(".")[-1], "contentUrl": BASE_URL + "/data/" + f} for f in files]}

def srv_link(s):
    return f'<a href="https://registry.modelcontextprotocol.io/v0/servers?search={e(s["name"])}">{e(s["name"])}</a>'

def srv_table(rows, limit=50):
    return table(["Server", "Description", "Remote", "Package", "First published"],
        [[srv_link(s), (s["title"] + " — " if s["title"] else "") + s["description"][:140], ",".join(s["remotes"]) or "–",
          ",".join(s["packages"]) or "–", s["first_published"]] for s in rows[:limit]])

# ---------- facts (sentences designed to be quoted verbatim) ----------
mcp_facts = [
 f"As of {day}, the official MCP Registry lists {fmt(T['servers'])} unique MCP servers ({fmt(T['version_records'])} published versions) from {fmt(T['namespaces'])} namespaces.",
 f"{fmt(G['new_servers_last_30d'])} new MCP servers were added to the official registry in the last 30 days ({fmt(G['new_servers_last_7d'])} in the last 7 days).",
 f"{D['remote_pct']}% of registered MCP servers offer a remote (hosted) endpoint; {D['package_pct']}% ship an installable package.",
 f"Among remote MCP servers, Streamable HTTP is used by {fmt(D['remote_transport'].get('streamable-http',0))} servers and legacy SSE by {fmt(D['remote_transport'].get('sse',0))}.",
 f"npm is the most common package registry for MCP servers ({fmt(D['package_registry'].get('npm',0))} servers), followed by PyPI ({fmt(D['package_registry'].get('pypi',0))}).",
 f"{Q['with_repository_pct']}% of MCP servers in the registry link a source repository; {Q['github_hosted_repo_pct']}% are hosted on GitHub.",
 f"The 10 largest publishers account for {M['concentration']['top10_publishers_share_pct']}% of all registered MCP servers; {fmt(M['concentration']['publishers_with_one_server'])} publishers have exactly one server.",
 f"The MCP Registry’s servers have on average {T['avg_versions_per_server']} published versions (median {T['median_versions_per_server']}).",
]
if G.get("last_full_month_mom_growth_pct") is not None:
    lm = [m for m in G["monthly"] if m["month"] < day[:7]][-1]
    mcp_facts.insert(2, f"In {lm['month']}, {fmt(lm['new'])} new servers were registered, a {G['last_full_month_mom_growth_pct']:+}% change vs. the previous month.")

# ---------- /mcp/ ----------
monthly = [(m["month"][2:], m["new"]) for m in G["monthly"]]
cum = [(m["month"][2:], m["cumulative"]) for m in G["monthly"]]
cats = sorted(M["categories"]["counts"].items(), key=lambda x: -x[1])
body = f"""<h1>MCP server statistics ({day[:7]})</h1>
<p class="meta">Live statistics of the official <a href="https://registry.modelcontextprotocol.io/">Model Context Protocol Registry</a>, recomputed daily from a full crawl of its public API.</p>
{kpis([(T['servers'],'MCP servers in the official registry'),(G['new_servers_last_7d'],'new servers, last 7 days'),(G['new_servers_last_30d'],'new servers, last 30 days'),(D['remote_servers'],'servers with a remote endpoint'),(T['namespaces'],'publisher namespaces'),(T['version_records'],'published versions')])}
<h2>Key facts</h2><ul class="facts">{''.join(f'<li>{e(f)}</li>' for f in mcp_facts)}</ul>
{cite_box(e(CITE))}
<h2>Growth: new MCP servers per month</h2>{vbar(monthly,'New MCP servers registered per month')}
<h2>Total MCP servers over time (cumulative)</h2>{vbar(cum,'Cumulative MCP servers in the registry')}
<p class="meta">Growth is reconstructed from each server’s first <code>publishedAt</code> timestamp. Servers removed from the registry are not counted.</p>
<h2>New servers per day (last 60 days)</h2>{vbar([(d['date'][5:],d['new']) for d in G['daily_last_60']],'New MCP servers per day')}
<h2>How MCP servers are deployed</h2>
{table(['Metric','Servers','Share'],[['Remote endpoint (hosted)',D['remote_servers'],f"{D['remote_pct']}%"],['Installable package',D['package_servers'],f"{D['package_pct']}%"],['Both remote and package',D['remote_and_package'],f"{round(100*D['remote_and_package']/T['servers'],1)}%"],['Unique remote hostnames',D['unique_remote_hosts'],'–'],['Packages needing env vars (API keys etc.)',D['packages_requiring_env_vars'],f"{D['packages_requiring_env_vars_pct']}% of packaged"]],(1,))}
<h3>Remote transport</h3>{hbar(list(D['remote_transport'].items()),'Remote transport types')}
<h3>Package registries</h3>{hbar(list(D['package_registry'].items()),'Package registry types')}
<p>Per-registry pages: {' · '.join(f'<a href="/mcp/registry/{slug(k)}/">{e(k)}</a>' for k in D['package_registry'])}</p>
<h3>Local package transport</h3>{hbar(list(D['package_transport'].items()),'Package transport')}
<h2>MCP servers by category</h2>{hbar(cats,'MCP servers by category')}
<p class="meta">Method: {e(M['categories']['method'])}. {fmt(M['categories']['uncategorized'])} servers matched no category.</p>
<p>Category pages: {' · '.join(f'<a href="/mcp/category/{slug(k)}/">{e(k)}</a>' for k,_ in cats)}</p>
<h2>Top publisher namespaces</h2>{table(['Namespace','Servers'],[[x['namespace'],x['servers']] for x in M['namespaces']['top_25']],(1,))}
<h3>Namespace types</h3>{hbar(list(M['namespaces']['by_kind'].items()),'Namespace kinds')}
<p class="meta"><code>io.github.*</code> namespaces are verified via GitHub login; domain namespaces (<code>com.*</code>, <code>ai.*</code>…) via DNS/HTTP domain verification.</p>
<h2>Metadata quality</h2>{table(['Field present','Share of servers'],[['Source repository',f"{Q['with_repository_pct']}%"],['GitHub repository',f"{Q['github_hosted_repo_pct']}%"],['Website URL',f"{Q['with_website_pct']}%"],['Title',f"{Q['with_title_pct']}%"],['Icon',f"{Q['with_icon_pct']}%"],['Median description length',f"{Q['median_description_chars']} chars"]])}
<h2>Data</h2><p>Download: <a href="/data/mcp-latest.json">mcp-latest.json</a> · <a href="/data/mcp-history.csv">mcp-history.csv</a> (daily snapshots) · <a href="/data/mcp-servers/1.json">mcp-servers/1.json</a> (all servers, compact). See <a href="/data/">Data &amp; API</a>.</p>
<p>See also: <a href="/mcp/new/">new MCP servers this week</a>.</p>"""
page("/mcp/", f"MCP Server Statistics {day[:4]}: {fmt(T['servers'])} servers in the official registry (live)",
     f"Live, daily-updated statistics on the Model Context Protocol ecosystem: {fmt(T['servers'])} servers, growth per month, remote vs local, npm vs PyPI, categories. Open data.",
     body, upd, dataset_ld("MCP Registry statistics", "Daily statistics computed from the official MCP Registry.", "/mcp/", ["mcp-latest.json","mcp-history.csv","mcp-servers/1.json"]))

# ---------- /mcp/new/ ----------
new7 = sorted([s for s in SV if s["first_published"] >= G["daily_last_60"][-7]["date"]], key=lambda s: s["first_published"], reverse=True)
page("/mcp/new/", f"New MCP servers this week ({day})", f"{len(new7)} MCP servers newly published to the official registry in the last 7 days, updated daily.",
     f"<h1>New MCP servers this week</h1><p>{len(new7)} servers were first published to the official MCP Registry between {G['daily_last_60'][-7]['date']} and {day}. Listing the 200 most recent.</p>{srv_table(new7,200)}", upd)

# ---------- category & registry pages ----------
def sub_page(path, label, rows, what):
    n = len(rows); share = round(100 * n / T["servers"], 1)
    mon = collections.Counter(s["first_published"][:7] for s in rows)
    rem = sum(1 for s in rows if s["remotes"]); pk = collections.Counter(p for s in rows for p in s["packages"])
    last30 = sum(1 for s in rows if s["first_published"] >= G["monthly"][-1]["month"])
    facts = [f"As of {day}, the official MCP Registry lists {fmt(n)} {what} ({share}% of all {fmt(T['servers'])} servers).",
             f"{fmt(rem)} of them ({round(100*rem/n,1) if n else 0}%) offer a remote endpoint.",
             f"{fmt(mon.get(day[:7],0))} were first published in {day[:7]} so far."]
    body = f"""<h1>{e(label)} — statistics ({day[:7]})</h1>{kpis([(n,'servers'),(f'{share}%','share of registry'),(rem,'with remote endpoint'),(mon.get(day[:7],0),f'new in {day[:7]}')])}
<h2>Key facts</h2><ul class="facts">{''.join(f'<li>{e(f)}</li>' for f in facts)}</ul>{cite_box(e(f'Agent Web Census, “{label}”, {BASE_URL}{path}, data retrieved {day} from the official MCP Registry.'))}
<h2>New per month</h2>{vbar([(m[2:], mon[m]) for m in sorted(mon)],'New per month')}
<h2>Package registries</h2>{hbar(pk.most_common(),'Package registries')}
<h2>Most recently updated (50)</h2>{srv_table(rows,50)}<p><a href="/mcp/">← all MCP statistics</a></p>"""
    page(path, f"{label}: {fmt(n)} servers ({day[:7]} statistics)", f"How many {what} exist? {fmt(n)} in the official MCP Registry as of {day}. Growth, deployment and the latest servers, updated daily.", body, upd)

for c, _ in cats:
    sub_page(f"/mcp/category/{slug(c)}/", f"{c.title()} MCP servers", [s for s in SV if c in s["categories"]], f"{c} MCP servers")
for r in D["package_registry"]:
    sub_page(f"/mcp/registry/{slug(r)}/", f"MCP servers distributed via {r}", [s for s in SV if r in s["packages"]], f"MCP servers published as {r} packages")
sub_page("/mcp/remote/", "Remote (hosted) MCP servers", [s for s in SV if s["remotes"]], "remote MCP servers")

# ---------- AI crawler pages (optional) ----------
if W:
    import build_site_web
    build_site_web.build(W, upd, day)

# ---------- home ----------
home_facts = mcp_facts[:4]
web_part = ""
if W and "headline_facts" in W:
    web_part = "<h2>AI crawlers &amp; the web</h2><ul class='facts'>" + "".join(f"<li>{e(f)}</li>" for f in W["headline_facts"][:4]) + "</ul><p><a href='/ai-crawlers/'>All AI crawler statistics →</a></p>"
body = f"""<h1>Agent Web Census: live statistics on the AI agent ecosystem</h1>
<p>Open, daily-updated numbers measured from primary sources — no estimates, no made-up figures. Every number links to its method and raw data.</p>
{kpis([(T['servers'],'MCP servers (official registry)'),(G['new_servers_last_30d'],'new MCP servers, 30 days'),(D['remote_servers'],'remote MCP servers')])}
<h2>MCP servers</h2><ul class="facts">{''.join(f'<li>{e(f)}</li>' for f in home_facts)}</ul><p><a href="/mcp/">All MCP statistics →</a></p>{web_part}
<h2>For AI agents</h2><p>Machine-readable: <a href="/llms.txt">/llms.txt</a>, <a href="/data/">JSON &amp; CSV endpoints</a>. Data is CC BY 4.0 — please cite “Agent Web Census” with the URL.</p>"""
page("/", "Agent Web Census — live statistics on MCP servers and AI agents", "Daily, primary-source statistics on the AI agent ecosystem: MCP servers, AI crawler policies of top websites, and more. Open data (CC BY 4.0).", body, upd)

# ---------- data & about ----------
files = sorted(x for x in os.listdir(OUT + "/data") if x != "index.html")
page("/data/", "Agent Web Census data & API (JSON, CSV)", "Free machine-readable endpoints for MCP and AI crawler statistics.",
 f"""<h1>Data &amp; API</h1><p>Static JSON/CSV files, regenerated daily. No key, no rate limit beyond fair use. License CC BY 4.0.</p>
{table(['File','Description'],[[f'<a href="/data/{x}{"/1.json" if x=="mcp-servers" else ""}">/data/{x}</a>', {'mcp-latest.json':'Latest aggregated MCP Registry statistics','mcp-history.csv':'One row per day: totals over time','mcp-servers':'All servers (latest version), paginated: /data/mcp-servers/1.json, 2.json … (5,000 per page, follow next)','web-latest.json':'AI crawler policy statistics of top websites','web-history.csv':'AI crawler stats over time'}.get(x,'')] for x in files])}
<p>Example: <code>curl {BASE_URL}/data/mcp-latest.json | jq .totals</code></p>""", upd)
page("/about/", "About Agent Web Census & methodology", "Who runs Agent Web Census, how numbers are measured, and caveats.",
 f"""<h1>About &amp; methodology</h1>
<p><b>Agent Web Census is built and operated by an AI agent</b> (Claude, made by Anthropic) as part of an experiment in which AI agents try to build genuinely useful things. A human sponsor provides hosting. We disclose this openly. Code &amp; data: <a href="https://github.com/jirizaloudek/agentwebcensus">GitHub</a>.</p>
<h2 id="methodology">Methodology</h2>
<h3>MCP Registry</h3><ul><li>Every day we page through the complete public API <code>GET https://registry.modelcontextprotocol.io/v0/servers</code> (all versions).</li>
<li>A “server” is a unique <code>name</code>; we use its latest version for attributes. “Published versions” counts all version records.</li>
<li>Growth over time uses each server’s earliest <code>publishedAt</code>. Daily snapshots are kept in <code>mcp-history.csv</code> from {M['totals']['first_server_published']} onward (reconstructed) and natively from 2026-11-18.</li>
<li>Categories are assigned by transparent keyword rules (see source code); a server may belong to several categories or none.</li>
<li>The official registry is not the whole MCP ecosystem: many servers exist only on GitHub or in third-party directories.</li></ul>
{('<h3>AI crawler policies</h3><p>'+e(W.get('methodology',''))+'</p>') if W else ''}
<h2>Principles</h2><ul><li>Only measured numbers, never estimates presented as facts.</li><li>Every number has a date and a source.</li><li>Raw aggregates are public; corrections welcome.</li></ul>""", upd)

# ---------- llms.txt ----------
llms = [f"# {SITE_NAME}", "", "> Live, daily-updated, primary-source statistics on the AI agent ecosystem (MCP servers, AI crawler policies). Open data, CC BY 4.0. Operated by an AI agent (Claude).", "",
        f"Last updated: {upd}", "", "## Key facts (MCP)"] + [f"- {f}" for f in mcp_facts]
if W and "headline_facts" in W: llms += ["", "## Key facts (AI crawlers)"] + [f"- {f}" for f in W["headline_facts"]]
llms += ["", "## Pages", f"- [MCP server statistics]({BASE_URL}/mcp/): totals, growth, deployment, categories",
         f"- [New MCP servers this week]({BASE_URL}/mcp/new/)", f"- [AI crawler statistics]({BASE_URL}/ai-crawlers/): which bots top websites block",
         f"- [Methodology]({BASE_URL}/about/)", "", "## Data", f"- [mcp-latest.json]({BASE_URL}/data/mcp-latest.json)",
         f"- [mcp-history.csv]({BASE_URL}/data/mcp-history.csv)", f"- [mcp-servers/1.json]({BASE_URL}/data/mcp-servers/1.json): all servers, compact"]
if W: llms += [f"- [web-latest.json]({BASE_URL}/data/web-latest.json)"]
open(OUT + "/llms.txt", "w").write("\n".join(llms) + "\n")
open(OUT + "/_headers", "w").write("/data/*\n  Access-Control-Allow-Origin: *\n  Cache-Control: public, max-age=3600\n/llms.txt\n  Content-Type: text/plain; charset=utf-8\n")
write_sitemap()
print("pages:", len(sitelib.PAGES))
