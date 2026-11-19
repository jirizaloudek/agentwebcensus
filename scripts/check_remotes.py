#!/usr/bin/env python3
"""Weekly liveness check of remote MCP servers (one initialize handshake per URL; never calls tools).
Usage: check_remotes.py --out data/health/raw.jsonl [--limit N] [--sample]"""
import argparse, json, os, random, socket, ssl, sys, threading, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, urljoin

UA = "AgentWebCensusBot/0.1 (+https://agents.datacensus.org/about/; weekly MCP liveness check, one initialize handshake)"
TIMEOUT, CAP, CONC, PER_HOST = 10, 256 * 1024, 48, 4
HDRS = {"User-Agent": UA, "Accept": "application/json, text/event-stream", "Content-Type": "application/json"}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
OPENER = urllib.request.build_opener(NoRedirect)

class Resp:  # uniform result of one HTTP exchange
    def __init__(s, status, headers, body): s.status, s.headers, s.body = status, headers, body

def classify_exc(ex):
    r = getattr(ex, "reason", ex)
    if isinstance(r, socket.gaierror): return "dns_error", "dns: " + str(r)[:80]
    if isinstance(r, ssl.SSLError) or "CERTIFICATE" in str(r).upper() or "SSL" in str(r).upper(): return "tls_error", str(r)[:100]
    if isinstance(r, (socket.timeout, TimeoutError)) or "timed out" in str(r): return "timeout", "timeout"
    return "conn_error", (type(r).__name__ + ": " + str(r))[:100]

def http(method, url, data=None, extra=None, read_cap=CAP):
    h = dict(HDRS); h.update(extra or {})
    for _ in range(4):  # follow up to 3 redirects, keeping method
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        try:
            r = OPENER.open(req, timeout=TIMEOUT); st, hd = r.status, r.headers
        except urllib.error.HTTPError as ex:
            st, hd, r = ex.code, ex.headers, ex
            if st in (301, 302, 303, 307, 308) and hd.get("Location"):
                url = urljoin(url, hd["Location"]); continue
        return Resp(st, hd, r.read(read_cap)), r
    return Resp(st, hd, b""), r

def parse_rpc(body, ctype):
    """JSON or SSE body -> first JSON-RPC response dict, or None."""
    txt = body.decode("utf-8", "replace").strip()
    if "event-stream" in (ctype or "") or txt.startswith(("data:", "event:", "id:")):
        for line in txt.splitlines():
            if line.startswith("data:"):
                try:
                    o = json.loads(line[5:].strip())
                    if isinstance(o, dict) and ("result" in o or "error" in o): return o
                except ValueError: pass
        return None
    try:
        o = json.loads(txt)
        if isinstance(o, list): o = next((x for x in o if isinstance(x, dict)), None)
        return o if isinstance(o, dict) else None
    except ValueError: return None

def rpc_body(method, id_=None, params=None):
    d = {"jsonrpc": "2.0", "method": method}
    if id_ is not None: d["id"] = id_
    if params is not None: d["params"] = params
    return json.dumps(d).encode()

def check_streamable(url):
    out = {"transport": "streamable-http"}
    t0 = time.time()
    init = rpc_body("initialize", 1, {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "AgentWebCensus", "version": "0.1"}})
    try:
        resp, _ = http("POST", url, init)
    except Exception as ex:
        out["outcome"], out["error"] = classify_exc(ex); out["latency_ms"] = int((time.time() - t0) * 1000); return out
    out["latency_ms"] = int((time.time() - t0) * 1000); out["http_status"] = resp.status
    if resp.status in (401, 403) or resp.headers.get("WWW-Authenticate"):
        out["outcome"] = "auth_required"; return out
    if not 200 <= resp.status < 300:
        out["outcome"], out["error"] = "http_error", f"HTTP {resp.status}"; return out
    o = parse_rpc(resp.body, resp.headers.get("Content-Type"))
    res = o.get("result") if o else None
    if not isinstance(res, dict) or "protocolVersion" not in res:
        out["outcome"] = "invalid_response"
        out["error"] = ("jsonrpc error: " + str((o.get("error") or {}).get("message", ""))[:80]) if o and "error" in o else "not an MCP initialize result"
        return out
    out["outcome"] = "ok"; out["protocol_version"] = res.get("protocolVersion")
    si = res.get("serverInfo") or {}
    out["server_name"] = str(si.get("name", ""))[:80] or None; out["server_version"] = str(si.get("version", ""))[:40] or None
    sess = resp.headers.get("Mcp-Session-Id")
    h = {"Mcp-Session-Id": sess} if sess else {}
    if out["protocol_version"]: h["MCP-Protocol-Version"] = out["protocol_version"]
    try:
        http("POST", url, rpc_body("notifications/initialized"), h)
        r2, _ = http("POST", url, rpc_body("tools/list", 2, {}), h)
        o2 = parse_rpc(r2.body, r2.headers.get("Content-Type"))
        tools = ((o2 or {}).get("result") or {}).get("tools")
        if isinstance(tools, list): out["tools_count"] = len(tools)
        elif o2 and "error" in o2: out["error"] = "tools/list: " + str((o2["error"] or {}).get("message", ""))[:80]
        elif r2.status in (401, 403): out["error"] = "tools/list: auth required"
    except Exception as ex:
        out["error"] = "tools/list: " + classify_exc(ex)[1]
    return out

def check_sse(url):
    out = {"transport": "sse"}; t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/event-stream"})
        try:
            r = OPENER.open(req, timeout=5); st = r.status
        except urllib.error.HTTPError as ex: r, st = ex, ex.code
        out["latency_ms"] = int((time.time() - t0) * 1000); out["http_status"] = st
        if st in (401, 403) or r.headers.get("WWW-Authenticate"): out["outcome"] = "auth_required"; return out
        if not 200 <= st < 300: out["outcome"], out["error"] = "http_error", f"HTTP {st}"; return out
        buf, dl = b"", time.time() + 5
        while time.time() < dl and len(buf) < 4096 and b"\n\n" not in buf and b"\r\n\r\n" not in buf:
            try: c = r.read1(1024) if hasattr(r, "read1") else r.read(1024)
            except (socket.timeout, TimeoutError): break
            if not c: break
            buf += c
        ok = "event-stream" in (r.headers.get("Content-Type") or "") or buf.lstrip().startswith((b"event:", b"data:"))
        out["outcome"] = "ok" if ok else "invalid_response"
        if not ok: out["error"] = "not an event stream"
    except Exception as ex:
        out["latency_ms"] = int((time.time() - t0) * 1000); out["outcome"], out["error"] = classify_exc(ex)
    return out

HOST_SEM, HL = {}, threading.Lock()
def work(job):
    host = urlparse(job["url"]).hostname or ""
    with HL: sem = HOST_SEM.setdefault(host, threading.Semaphore(PER_HOST))
    with sem:
        try: r = check_sse(job["url"]) if job["sse"] else check_streamable(job["url"])
        except Exception as ex: r = {"outcome": "conn_error", "error": f"internal: {ex}"[:100]}
    rec = {"name": job["name"], "url": job["url"], "host": host, "transport": r.get("transport"), "http_status": r.get("http_status"),
           "outcome": r["outcome"], "latency_ms": r.get("latency_ms"), "protocol_version": r.get("protocol_version"),
           "server_name": r.get("server_name"), "server_version": r.get("server_version"), "tools_count": r.get("tools_count"),
           "error": r.get("error"), "checked": time.strftime("%Y-%m-%d", time.gmtime())}
    return rec

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--limit", type=int)
    ap.add_argument("--sample", action="store_true"); ap.add_argument("--servers", default="data/mcp/servers.json")
    a = ap.parse_args()
    S = json.load(open(a.servers)); seen, jobs = set(), []
    for s in S:
        if not s.get("remote_urls"): continue
        u = s["remote_urls"][0]
        if u in seen: continue
        seen.add(u); jobs.append({"name": s["name"], "url": u, "sse": (s.get("remotes") or [""])[0] == "sse"})
    if a.sample: random.Random(1).shuffle(jobs)
    if a.limit: jobs = jobs[:a.limit]
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            try: done.add(json.loads(l)["url"])
            except Exception: pass
    todo = [j for j in jobs if j["url"] not in done]; random.Random(2).shuffle(todo)  # spread load across hosts
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    print(f"{len(jobs)} unique URLs, {len(done)} already done, {len(todo)} to check", file=sys.stderr)
    lock, n, t0 = threading.Lock(), 0, time.time()
    with open(a.out, "a") as f, ThreadPoolExecutor(CONC) as ex:
        for rec in ex.map(work, todo):
            with lock:
                f.write(json.dumps(rec, separators=(",", ":")) + "\n"); f.flush(); n += 1
            if n % 200 == 0: print(f"{n}/{len(todo)} {time.time()-t0:.0f}s", file=sys.stderr)
    print(f"done {n} in {time.time()-t0:.0f}s", file=sys.stderr)

if __name__ == "__main__": main()
