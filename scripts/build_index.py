#!/usr/bin/env python3
"""Write compact lookup indexes for the MCP worker into site/data/ (sharded idx/ and sites/)."""
import json, os

OUT = "site/data"
import re, shutil, collections

DESC_MAX = 160
STOP = set("the and for with that this from your you are can use using via any all not but our out its has have will how what when into over more also new per such than then their them they these those which who why able based only just like one two get set run make made need see".split())
MAX_DF = 0.08
RANK = {"ok": 0, "auth": 1, None: 2, "fail": 3}
TOKRE = re.compile(r"[a-z0-9]+")


def shard(tok):
    """FNV-1a 32-bit of the token (UTF-8), low 8 bits; mirrored in worker/src/index.js."""
    h = 2166136261
    for b in tok.encode():
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h & 1023


def tokens(text):
    return {t for t in TOKRE.findall(text.lower()) if len(t) >= 3}


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)


def build_mcp_index():
    servers = json.load(open("data/mcp/servers.json"))
    health = {}
    if os.path.exists("data/health/servers.json"):
        for h in json.load(open("data/health/servers.json")):
            o = h.get("outcome")
            o = "ok" if o == "ok" else "auth" if o == "auth_required" else "fail"
            cur = health.get(h["name"])
            if cur is None or RANK[o] < RANK[cur[0]]:
                health[h["name"]] = (o, h.get("tools_count"), h.get("latency_ms"))
    rows = []
    for s in servers:
        if s.get("status") == "deprecated" or (not s.get("remotes") and not s.get("packages")):
            continue
        h = health.get(s["name"], (None, None, None))
        rows.append([s["name"], s.get("title") or "", (s.get("description") or "")[:DESC_MAX].replace("\n", " "),
                     ",".join(s.get("categories") or []), ",".join(s.get("remotes") or []),
                     ",".join(s.get("packages") or []), h[0], h[1], h[2], s.get("first_published") or ""])
    # id = quality rank (working first, then more tools), so low ids are the best candidates
    rows.sort(key=lambda r: (RANK[r[6]], -(r[7] or 0), r[0]))
    d = "%s/idx" % OUT
    shutil.rmtree(d, ignore_errors=True)
    for i in range(0, len(rows), 64):
        chunk = rows[i:i + 64]
        dump("%s/rec/%03x.json" % (d, i // 64), chunk)
    n = len(rows)
    df, post = collections.Counter(), collections.defaultdict(list)
    for i, r in enumerate(rows):
        for t in tokens(" ".join([r[0].split("/", 1)[-1], r[1], r[2], r[3]])):  # skip namespace (io.github.*)
            post[t].append(i)
    skip = sorted(t for t, ids in post.items() if t in STOP or len(ids) > MAX_DF * n)
    for t in skip:
        del post[t]
    shards = [dict() for _ in range(1024)]
    for t, ids in post.items():
        shards[shard(t)][t] = ids
    for k, sh in enumerate(shards):
        dump("%s/tok/%03x.json" % (d, k), sh)
    cats = collections.defaultdict(list)
    for i, r in enumerate(rows):
        for c in filter(None, r[3].split(",")):
            if len(cats[c]) < 100:
                cats[c].append(i)
    dump(d + "/meta.json", {"date": datetime_today(), "servers": n, "rec_shard": "id>>6 -> array of 64 rows",
                            "record": ["name", "title", "description", "categories", "remotes", "packages", "health", "tools", "latency_ms", "first_published"],
                            "skip": skip, "categories": cats})
    return n


def datetime_today():
    try:
        return json.load(open("data/health/latest.json"))["generated"]
    except Exception:
        return ""


def build_sites_index():
    d = json.load(open("data/web/domains.json"))
    out = collections.defaultdict(dict)
    for r in d["domains"]:
        flags = (1 if r.get("l") else 0) | (2 if r.get("s") else 0)
        c = r["d"][0] if r["d"][0].isalnum() and r["d"][0].isascii() else "_"
        out[c][r["d"]] = [r["r"], r["rb"], flags] + [f"{b}:{c2}" for b, c2 in (r.get("b") or {}).items()]
    shutil.rmtree(OUT + "/sites", ignore_errors=True)
    for c in list("abcdefghijklmnopqrstuvwxyz0123456789_"):  # always write every shard: a 404 then means data missing, not "domain not scanned"
        doms = out.get(c, {})
        dump(f"{OUT}/sites/{c}.json", {"date": d["generated"], "codes": d["codes"], "domains": doms})
    return sum(len(v) for v in out.values())


def main():
    os.makedirs(OUT, exist_ok=True)
    for old in ("mcp-index.json", "sites-index.json"):
        if os.path.exists(f"{OUT}/{old}"):
            os.remove(f"{OUT}/{old}")
    print("idx records:", build_mcp_index())
    print("sites indexed:", build_sites_index())


if __name__ == "__main__":
    main()
