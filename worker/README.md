# datacensus-mcp: Agent Web Census MCP server

Dependency-free Cloudflare Worker (ES module) implementing a stateless MCP server over Streamable HTTP
(`POST /mcp`, JSON responses, no SSE). Tools: `find_mcp_servers`, `mcp_ecosystem_stats`,
`site_ai_crawler_policy`, `ai_crawler_stats`. Data is fetched from `DATA_BASE`
(default `https://agents.datacensus.org/data/`) and cached for an hour (Cache API + in-memory).

The Worker needs the sharded indexes `idx/` (1024 token shards up to ~40 KB, 1018 record shards of ~17 KB, meta) and `sites/` (one file per first letter), produced by `scripts/build_index.py`
(called from `scripts/build_site.py`). Each request parses only a handful of small shards, so it fits the Free plan (10 ms CPU).

## Local test

    python3 scripts/build_site.py
    (cd site/data && python3 -m http.server 8801 &)
    cd worker && npx wrangler@3 dev src/index.js --local --port 8787 --var DATA_BASE:http://localhost:8801/
    curl -s localhost:8787/mcp -H 'Content-Type: application/json' -H 'Accept: application/json' \
      -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

## Deploy

Create an API token (My Profile, API Tokens) with **Account / Workers Scripts: Edit** and
**Zone / Workers Routes: Edit** (zone datacensus.org). Then:

    cd worker
    export CLOUDFLARE_API_TOKEN=...      # and CLOUDFLARE_ACCOUNT_ID=... if the token spans several accounts
    npx wrangler@3 deploy

Route: uncomment `routes` in `wrangler.toml` (`datacensus.org/*`, zone datacensus.org). The zone must be on
Cloudflare with a proxied (orange-cloud) DNS record for the apex (a dummy `A 192.0.2.1` works).

Without wrangler, via the API directly:

    curl -X PUT "https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID/workers/scripts/datacensus-mcp" \
      -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
      -F 'metadata={"main_module":"index.js","compatibility_date":"2026-11-01","bindings":[{"type":"plain_text","name":"DATA_BASE","text":"https://agents.datacensus.org/data/"}]};type=application/json' \
      -F 'index.js=@src/index.js;filename=index.js;type=application/javascript+module'
    curl -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/workers/routes" \
      -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" -H 'Content-Type: application/json' \
      -d '{"pattern":"datacensus.org/*","script":"datacensus-mcp"}'

Verify: `curl -s https://datacensus.org/mcp -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'`

Registry publishing: `server.json` at the repo root (`org.datacensus/agents`) is submitted with `mcp-publisher`
after verifying the `datacensus.org` namespace by DNS TXT or `/.well-known/mcp-registry-auth`.
