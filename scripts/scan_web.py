#!/usr/bin/env python3
"""Polite scanner: robots.txt + llms.txt of the Tranco top-N domains.

usage: python3 scripts/scan_web.py --top 10000 --out data/web/raw.jsonl
Per domain: robots.txt (+ www. fallback on connection error) and llms.txt. Nothing else.
Resumable: domains already present in --out are skipped.
"""
import argparse, csv, io, json, os, socket, ssl, sys, threading, time, urllib.error, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = ("AgentWebCensusBot/0.1 (+https://jirizaloudek.github.io/agentwebcensus/about/; "
      "open-data research on AI-crawler policies; fetches robots.txt and llms.txt only)")
MAX_BODY = 500 * 1024
KEEP_TEXT = 200 * 1024
TIMEOUT = 10


def fetch(url):
    """Return (status, content_type, body_bytes). status is int or 'error:<kind>'."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/plain, text/markdown, */*;q=0.5"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read(MAX_BODY)
            return r.status, r.headers.get("Content-Type", ""), body
    except urllib.error.HTTPError as e:
        try:
            body = e.read(2048)
        except Exception:
            body = b""
        return e.code, e.headers.get("Content-Type", "") if e.headers else "", body
    except urllib.error.URLError as e:
        r = e.reason
        if isinstance(r, (socket.timeout, TimeoutError)):
            return "error:timeout", "", b""
        if isinstance(r, ssl.SSLError):
            return "error:ssl", "", b""
        if isinstance(r, socket.gaierror):
            return "error:dns", "", b""
        if isinstance(r, ConnectionRefusedError):
            return "error:refused", "", b""
        return "error:conn", "", b""
    except (socket.timeout, TimeoutError):
        return "error:timeout", "", b""
    except Exception as e:
        return "error:" + type(e).__name__.lower(), "", b""


def decode(body):
    return body.decode("utf-8", errors="replace")


def llms_valid(status, ctype, body):
    if status != 200:
        return False
    ct = ctype.lower()
    if not ("text/markdown" in ct or "text/plain" in ct):
        return False
    t = decode(body).lstrip("﻿ \t\r\n")
    if not t.startswith("#"):
        return False
    head = t[:1000].lower()
    if "<html" in head or "<!doctype" in head or "<body" in head:
        return False
    return True


def scan(rank, domain):
    host = domain
    rs, _, rb = fetch(f"https://{domain}/robots.txt")
    if isinstance(rs, str) and rs.startswith("error:"):
        # connection-level error: try www. once (skip if already www.)
        if not domain.startswith("www."):
            rs2, _, rb2 = fetch(f"https://www.{domain}/robots.txt")
            if not (isinstance(rs2, str) and rs2.startswith("error:")):
                host, rs, rb = "www." + domain, rs2, rb2
    ls, lct, lb = fetch(f"https://{host}/llms.txt")
    return {
        "rank": rank, "domain": domain, "host": host,
        "robots_status": rs, "robots_bytes": len(rb),
        "robots_text": decode(rb)[:KEEP_TEXT] if rs == 200 else "",
        "llms_status": ls, "llms_is_valid": llms_valid(ls, lct, lb), "llms_bytes": len(lb) if ls == 200 else 0,
    }


def load_tranco(n, outdir):
    meta_path = os.path.join(outdir, "tranco_meta.json")
    list_id = None
    try:
        req = urllib.request.Request("https://tranco-list.eu/top-1m-id", headers={"User-Agent": UA})
        list_id = urllib.request.urlopen(req, timeout=30).read().decode().strip()
    except Exception as e:
        print("could not fetch list id:", e, file=sys.stderr)
    req = urllib.request.Request("https://tranco-list.eu/top-1m.csv.zip", headers={"User-Agent": UA})
    data = urllib.request.urlopen(req, timeout=120).read()
    z = zipfile.ZipFile(io.BytesIO(data))
    rows = []
    with z.open(z.namelist()[0]) as f:
        for row in csv.reader(io.TextIOWrapper(f, encoding="utf-8")):
            if len(row) >= 2:
                rows.append((int(row[0]), row[1].strip().lower()))
                if len(rows) >= n:
                    break
    with open(meta_path, "w") as f:
        json.dump({"tranco_list_id": list_id, "downloaded": time.strftime("%Y-%m-%d"), "top_n": n}, f)
    print(f"tranco list id={list_id} domains={len(rows)}", file=sys.stderr)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10000)
    ap.add_argument("--out", default="data/web/raw.jsonl")
    ap.add_argument("--workers", type=int, default=32)
    a = ap.parse_args()
    outdir = os.path.dirname(a.out) or "."
    os.makedirs(outdir, exist_ok=True)
    done = set()
    if os.path.exists(a.out):
        with open(a.out) as f:
            for line in f:
                try:
                    done.add(json.loads(line)["domain"])
                except Exception:
                    pass
    todo = [(r, d) for r, d in load_tranco(a.top, outdir) if d not in done]
    print(f"to scan: {len(todo)} (already done: {len(done)})", file=sys.stderr)
    lock = threading.Lock()
    t0 = time.time()
    n = 0
    with open(a.out, "a") as out, ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(scan, r, d) for r, d in todo]
        for fu in as_completed(futs):
            try:
                rec = fu.result()
            except Exception as e:
                continue
            with lock:
                out.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
                out.flush()
            n += 1
            if n % 100 == 0:
                print(f"{n}/{len(todo)} {time.time()-t0:.0f}s", file=sys.stderr)
    print(f"done {n} in {time.time()-t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
