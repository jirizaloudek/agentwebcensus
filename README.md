# Agent Web Census

Live, daily-updated, **measured** statistics on the AI agent ecosystem — no estimates, no made-up numbers.

- **MCP servers**: full daily crawl of the official [MCP Registry](https://registry.modelcontextprotocol.io/) → totals, growth, deployment (remote vs. package), registries, categories, publishers.
- **AI crawlers & the web**: weekly scan of `robots.txt` and `llms.txt` on the top 10,000 websites ([Tranco](https://tranco-list.eu/)) → who blocks GPTBot, ClaudeBot, Google-Extended, CCBot…

Site: GitHub Pages (built by `.github/workflows/update.yml`). Data: `data/*/latest.json`, `data/*/history.csv` — **CC BY 4.0**, cite as “Agent Web Census”.

## Transparency
This project is built and operated by an AI agent (Claude, by Anthropic) with a human sponsor. The scanner identifies itself as `AgentWebCensusBot` and fetches only `robots.txt` and `llms.txt` (max 3 requests per domain per week).

## Run locally
```
python3 scripts/fetch_registry.py data/raw/registry.jsonl
python3 scripts/build_mcp_stats.py data/raw/registry.jsonl
python3 scripts/scan_web.py --top 10000 --out data/web/raw.jsonl && python3 scripts/build_web_stats.py
python3 scripts/build_site.py   # -> site/
```
