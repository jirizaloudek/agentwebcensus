#!/usr/bin/env python3
"""Build data/web/latest.json and update data/web/history.csv from data/web/raw.jsonl.

usage: python3 scripts/build_web_stats.py [--raw data/web/raw.jsonl] [--outdir data/web]
"""
import argparse, csv, datetime, json, os, re
from collections import Counter, defaultdict

# token -> (operator, purpose)
AI_BOTS = {
    "GPTBot": ("OpenAI", "training"),
    "ChatGPT-User": ("OpenAI", "user-triggered"),
    "OAI-SearchBot": ("OpenAI", "search"),
    "ClaudeBot": ("Anthropic", "training"),
    "Claude-User": ("Anthropic", "user-triggered"),
    "Claude-SearchBot": ("Anthropic", "search"),
    "anthropic-ai": ("Anthropic", "training"),
    "Claude-Web": ("Anthropic", "user-triggered"),
    "Google-Extended": ("Google", "training"),
    "Googlebot": ("Google", "search"),  # comparison only, not an AI bot
    "Applebot-Extended": ("Apple", "training"),
    "PerplexityBot": ("Perplexity", "search"),
    "Perplexity-User": ("Perplexity", "user-triggered"),
    "CCBot": ("Common Crawl", "training"),
    "Bytespider": ("ByteDance", "training"),
    "Amazonbot": ("Amazon", "training"),
    "Meta-ExternalAgent": ("Meta", "training"),
    "FacebookBot": ("Meta", "training"),
    "cohere-ai": ("Cohere", "user-triggered"),
    "DuckAssistBot": ("DuckDuckGo", "user-triggered"),
    "MistralAI-User": ("Mistral", "user-triggered"),
    "YouBot": ("You.com", "search"),
    "Diffbot": ("Diffbot", "training"),
    "Timpibot": ("Timpi", "training"),
    "ImagesiftBot": ("Hive/Imagesift", "training"),
    "omgili": ("Webz.io", "training"),
    "AI2Bot": ("Allen Institute for AI", "training"),
    "PetalBot": ("Huawei", "search"),
}
COMPARISON = {"Googlebot"}
AI_ONLY = [b for b in AI_BOTS if b not in COMPARISON]
CORE4 = ["GPTBot", "ClaudeBot", "Google-Extended", "CCBot"]
LOWER = {b.lower(): b for b in AI_BOTS}
BUCKETS = [("top100", 100), ("top1k", 1000), ("top10k", 10000)]
STATUSES = ["blocked_fully", "blocked_partially", "allowed_explicitly", "not_mentioned"]


def looks_html(text):
    head = text[:2000].lstrip("﻿ \t\r\n").lower()
    return head.startswith("<") or "<html" in head or "<!doctype" in head or "<body" in head


def parse_robots(text):
    """Return (groups, content_signals). groups: list of (set(lower UAs), [(directive, value)])."""
    text = text.lstrip("﻿")
    groups, cur_uas, cur_rules, in_rules = [], [], [], False
    signals = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip().lower(), v.strip()
        if k == "user-agent":
            if in_rules:
                groups.append((cur_uas, cur_rules))
                cur_uas, cur_rules, in_rules = [], [], False
            cur_uas.append(v.lower())
        elif k in ("allow", "disallow"):
            if cur_uas:
                cur_rules.append((k, v))
                in_rules = True
        elif k == "content-signal":
            signals.append(v)
    if cur_uas:
        groups.append((cur_uas, cur_rules))
    return groups, signals


def rules_for(groups, ua_lower):
    """Merged rules from all groups naming this UA; None if no group names it."""
    found, rules = False, []
    for uas, rs in groups:
        if ua_lower in uas:
            found = True
            rules.extend(rs)
    return rules if found else None


def classify_rules(rules):
    """-> 'blocked_fully' | 'blocked_partially' | 'allowed_explicitly' for a group that names the UA."""
    dis = [v for k, v in rules if k == "disallow" and v]
    allow_all = any(k == "allow" and v in ("/", "/*") for k, v in rules)
    if any(v in ("/", "/*") for v in dis) and not allow_all:
        return "blocked_fully"
    if dis and not allow_all:
        return "blocked_partially"
    if dis and allow_all:
        return "blocked_partially" if not any(v in ("/", "/*") for v in dis) else "allowed_explicitly"
    return "allowed_explicitly"


def star_blocks_all(groups):
    r = rules_for(groups, "*")
    return bool(r) and classify_rules(r) == "blocked_fully"


def analyze(rec):
    """Return per-domain analysis dict or None if no usable robots.txt."""
    if rec.get("robots_status") != 200:
        return None
    text = rec.get("robots_text") or ""
    if not text.strip() or looks_html(text):
        return None
    groups, signals = parse_robots(text)
    star = star_blocks_all(groups)
    res = {}
    for ua_l, bot in LOWER.items():
        r = rules_for(groups, ua_l)
        res[bot] = "not_mentioned" if r is None else classify_rules(r)
    sig = {}
    for s in signals:
        for part in s.split(","):
            if "=" in part:
                a, b = part.split("=", 1)
                sig[a.strip().lower()] = b.strip().lower()
    return {"bots": res, "star_blocks_all": star, "signals": bool(signals), "signal_kv": sig}


def pct(n, d):
    return round(100.0 * n / d, 2) if d else None


def summarize(items, total):
    """items: list of analyses (reachable). total: number of scanned domains in the group."""
    n = len(items)
    out = {"scanned": total, "robots_reachable": n, "bots": {}}
    for bot in AI_BOTS:
        c = Counter(a["bots"][bot] for a in items)
        nm_star = sum(1 for a in items if a["bots"][bot] == "not_mentioned" and a["star_blocks_all"])
        out["bots"][bot] = {
            "blocked_fully": c["blocked_fully"], "blocked_partially": c["blocked_partially"],
            "allowed_explicitly": c["allowed_explicitly"], "not_mentioned": c["not_mentioned"],
            "not_mentioned_but_star_blocks_all": nm_star,
            "pct_fully_of_reachable": pct(c["blocked_fully"], n),
            "pct_partially_of_reachable": pct(c["blocked_partially"], n),
            "pct_allowed_explicitly_of_reachable": pct(c["allowed_explicitly"], n),
            "pct_fully_of_all_scanned": pct(c["blocked_fully"], total),
            "pct_partially_of_all_scanned": pct(c["blocked_partially"], total),
            "pct_allowed_explicitly_of_all_scanned": pct(c["allowed_explicitly"], total),
        }
    any_block = sum(1 for a in items if any(a["bots"][b] == "blocked_fully" for b in AI_ONLY))
    any_touch = sum(1 for a in items if any(a["bots"][b] in ("blocked_fully", "blocked_partially") for b in AI_ONLY))
    core = sum(1 for a in items if all(a["bots"][b] == "blocked_fully" for b in CORE4))
    out["blocking_at_least_one_ai_bot_fully"] = {"count": any_block, "pct_of_reachable": pct(any_block, n), "pct_of_all_scanned": pct(any_block, total)}
    out["restricting_at_least_one_ai_bot_fully_or_partially"] = {"count": any_touch, "pct_of_reachable": pct(any_touch, n)}
    out["blocking_all_of_GPTBot_ClaudeBot_Google-Extended_CCBot"] = {"count": core, "pct_of_reachable": pct(core, n), "pct_of_all_scanned": pct(core, total)}
    out["star_blocks_everything"] = {"count": sum(1 for a in items if a["star_blocks_all"]), "pct_of_reachable": pct(sum(1 for a in items if a["star_blocks_all"]), n)}
    named = [sum(1 for b in AI_ONLY if a["bots"][b] != "not_mentioned") for a in items]
    out["mean_ai_bots_named_per_robots_txt"] = round(sum(named) / n, 3) if n else None
    out["mean_ai_bots_named_per_robots_txt_among_those_naming_any"] = (
        round(sum(x for x in named if x) / max(1, sum(1 for x in named if x)), 3) if n else None)
    return out


def tld(domain):
    return domain.rsplit(".", 1)[-1]


METHODOLOGY = (
    "Scanned the top-N domains of the Tranco list (list ID in tranco_list_id). For each domain we made at most "
    "three polite HTTPS GET requests (UA AgentWebCensusBot/0.1): https://<domain>/robots.txt (with one retry on "
    "https://www.<domain>/robots.txt only after a connection-level error) and /llms.txt on the host that answered. "
    "10 s timeout, redirects followed, body capped at 500 KB. A robots.txt counts as 'reachable' only if HTTP 200 "
    "and the body is non-empty and not HTML (soft-404 HTML pages are treated as invalid/no rules). robots.txt is parsed "
    "per RFC 9309 in a simplified way: consecutive User-agent lines form a group; rules of all groups naming the same "
    "token are merged; token matching is case-insensitive and exact (no substring/product-version matching); comments, "
    "BOM and CRLF are handled. Per bot: blocked_fully = a group naming the bot has Disallow: / (or /*) with no Allow: /; "
    "blocked_partially = it has other non-empty Disallow rules (or Disallow: / overridden by specific Allow rules is NOT "
    "counted as fully blocked); allowed_explicitly = a group naming the bot with no effective disallow; not_mentioned = no "
    "group names the bot, so it falls back to the '*' group (we record separately how many of those are covered by a "
    "'*' block-all). Wildcard patterns, longest-match precedence and Allow/Disallow interplay inside paths are not fully "
    "evaluated. Percentages are given both over domains with a reachable robots.txt and over all scanned domains (the "
    "latter counts unreachable sites as not blocking). 'AI bots' aggregates exclude Googlebot (comparison only). "
    "llms.txt is 'valid' if HTTP 200, content-type text/markdown or text/plain, the body starts with '#' and is not HTML; "
    "content quality is not assessed. Content-Signal counts any 'Content-Signal:' line in robots.txt (Cloudflare content "
    "signals: search / ai-input / ai-train). Caveats: robots.txt is a voluntary request, not enforcement; sites may block "
    "by other means (WAF, UA filtering, 403 for our bot) which robots.txt does not show, and some sites serve different "
    "robots.txt to different clients or block our scanner (counted as unreachable); network errors and timeouts are "
    "counted as unreachable; TLD is the last DNS label (co.uk counts as uk); rank buckets are cumulative (top1k includes top100)."
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/web/raw.jsonl")
    ap.add_argument("--outdir", default="data/web")
    a = ap.parse_args()
    recs = {}
    with open(a.raw) as f:
        for line in f:
            try:
                r = json.loads(line)
                recs[r["domain"]] = r
            except Exception:
                pass
    recs = sorted(recs.values(), key=lambda r: r["rank"])
    meta = {}
    mp = os.path.join(a.outdir, "tranco_meta.json")
    if os.path.exists(mp):
        meta = json.load(open(mp))
    for r in recs:
        r["_a"] = analyze(r)
    reach = [r for r in recs if r["_a"]]

    status_counts = Counter()
    for r in recs:
        s = r["robots_status"]
        status_counts[str(s) if isinstance(s, int) else s] += 1
    invalid_html = sum(1 for r in recs if r["robots_status"] == 200 and not r["_a"])

    overall = summarize([r["_a"] for r in reach], len(recs))
    by_bucket = {}
    for name, lim in BUCKETS:
        sub = [r for r in recs if r["rank"] <= lim]
        if sub:
            by_bucket[name] = summarize([r["_a"] for r in sub if r["_a"]], len(sub))
    tld_counts = Counter(tld(r["domain"]) for r in recs)
    tlds = [t for t, _ in tld_counts.most_common(20)]
    for t in ("cz", "de", "uk"):
        if t in tld_counts and t not in tlds:
            tlds.append(t)
    by_tld = {t: summarize([r["_a"] for r in recs if tld(r["domain"]) == t and r["_a"]], tld_counts[t]) for t in tlds}

    def llms(sub):
        n = len(sub)
        v = sum(1 for r in sub if r["llms_is_valid"])
        ok = sum(1 for r in sub if r["llms_status"] == 200)
        return {"scanned": n, "valid": v, "pct_valid": pct(v, n), "http200": ok, "pct_http200": pct(ok, n)}
    llms_stats = {"overall": llms(recs), "by_rank_bucket": {n: llms([r for r in recs if r["rank"] <= l]) for n, l in BUCKETS if any(r["rank"] <= l for r in recs)}}

    ns = len(reach)
    with_sig = [r for r in reach if r["_a"]["signals"]]
    kv = defaultdict(Counter)
    for r in with_sig:
        for k, v in r["_a"]["signal_kv"].items():
            kv[k][v] += 1
    content_signal = {"count": len(with_sig), "pct_of_reachable": pct(len(with_sig), ns),
                      "pct_of_all_scanned": pct(len(with_sig), len(recs)),
                      "values": {k: dict(c) for k, c in kv.items()}}

    today = datetime.date.today().isoformat()
    latest = {
        "generated": today,
        "tranco_list_id": meta.get("tranco_list_id"),
        "tranco_downloaded": meta.get("downloaded"),
        "domains_scanned": len(recs),
        "max_rank_scanned": max((r["rank"] for r in recs), default=0),
        "robots_reachable": ns,
        "robots_reachable_pct": pct(ns, len(recs)),
        "robots_http200_but_invalid_or_html": invalid_html,
        "robots_status_counts": dict(status_counts.most_common()),
        "bots_catalog": {b: {"operator": o, "purpose": p, "comparison_only": b in COMPARISON} for b, (o, p) in AI_BOTS.items()},
        "overall": overall,
        "by_rank_bucket": by_bucket,
        "by_tld": by_tld,
        "llms_txt": llms_stats,
        "content_signal": content_signal,
        "methodology": METHODOLOGY,
    }
    with open(os.path.join(a.outdir, "latest.json"), "w") as f:
        json.dump(latest, f, indent=1, ensure_ascii=False)

    # history.csv
    b = overall["bots"]
    row = {
        "date": today, "tranco_list_id": meta.get("tranco_list_id") or "", "scanned": len(recs), "robots_reachable": ns,
        "gptbot_fully_pct": b["GPTBot"]["pct_fully_of_reachable"],
        "claudebot_fully_pct": b["ClaudeBot"]["pct_fully_of_reachable"],
        "google_extended_fully_pct": b["Google-Extended"]["pct_fully_of_reachable"],
        "ccbot_fully_pct": b["CCBot"]["pct_fully_of_reachable"],
        "any_ai_bot_fully_pct": overall["blocking_at_least_one_ai_bot_fully"]["pct_of_reachable"],
        "all_core4_fully_pct": overall["blocking_all_of_GPTBot_ClaudeBot_Google-Extended_CCBot"]["pct_of_reachable"],
        "mean_ai_bots_named": overall["mean_ai_bots_named_per_robots_txt"],
        "llms_txt_valid_pct": llms_stats["overall"]["pct_valid"],
        "content_signal_pct": content_signal["pct_of_reachable"],
    }
    hp = os.path.join(a.outdir, "history.csv")
    rows = []
    if os.path.exists(hp):
        with open(hp, newline="") as f:
            rows = [r for r in csv.DictReader(f) if r["date"] != today]
    rows.append({k: str(v) for k, v in row.items()})
    with open(hp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        w.writeheader()
        w.writerows(rows)
    print(json.dumps({k: latest[k] for k in ("domains_scanned", "robots_reachable", "robots_reachable_pct")}))
    print("llms valid %:", llms_stats["overall"]["pct_valid"], "content-signal %:", content_signal["pct_of_reachable"])
    print("any AI bot fully blocked %:", row["any_ai_bot_fully_pct"], " core4 %:", row["all_core4_fully_pct"], "mean named:", row["mean_ai_bots_named"])
    for k in ("GPTBot", "ClaudeBot", "Google-Extended", "CCBot", "Googlebot", "Bytespider"):
        print(k, {x: b[k][x] for x in ("pct_fully_of_reachable", "pct_partially_of_reachable", "pct_allowed_explicitly_of_reachable")})


if __name__ == "__main__":
    main()
