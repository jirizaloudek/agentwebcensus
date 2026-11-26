#!/usr/bin/env python3
"""Central bank policy rates + decision calendar (data/stats/cb_rates.json).

Inputs:
  data/stats/cb_calendar.json  hand-curated official meeting dates (decision announcement days), with source URLs
  data/stats/latest.json       BIS policy rates (fallback when no official daily feed)
Official daily feeds (newer than BIS, which lags ~1 week): ECB data API, FRED (Fed target range),
Bank of England IADB, Bank of Canada Valet, SNB data portal. Latest monetary-policy press releases from
official RSS feeds (titles are external text: stored as plain data, HTML-escaped when rendered).
Daily history of each rate is accumulated in the output file (2 years). Never fails the workflow."""
import csv, datetime as dt, io, json, re, sys, urllib.request
from html import unescape

OUT = "data/stats/cb_rates.json"
UA = "agentwebcensus/1.0 (+https://agents.datacensus.org)"
TODAY = dt.date.today()
WARN = []


def get(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8-sig", "replace")


def f2(v):
    return round(float(v), 4)


# ------------------------------------------------------------ official daily feeds
def ecb():
    out = {}
    for key, code in (("deposit_facility", "DFR"), ("main_refinancing", "MRR_FR"), ("marginal_lending", "MLFR")):
        rows = csv.DictReader(io.StringIO(get(f"https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.{code}.LEV?lastNObservations=400&format=csvdata")))
        out[key] = {r["TIME_PERIOD"]: f2(r["OBS_VALUE"]) for r in rows if r.get("OBS_VALUE")}
    return {"series": out["deposit_facility"], "rate_label": "Deposit facility rate (the ECB's policy rate)",
            "extra": {k: max(v.items()) for k, v in out.items() if v and k != "deposit_facility"},
            "source": "ECB Data Portal, key ECB interest rates (FM.D.U2.EUR.4F.KR.DFR.LEV)",
            "source_url": "https://data.ecb.europa.eu/data/datasets/FM"}


def fred(series_id):
    rows = csv.reader(io.StringIO(get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={(TODAY - dt.timedelta(days=760)).isoformat()}")))
    next(rows, None)
    return {r[0]: f2(r[1]) for r in rows if len(r) > 1 and re.match(r"^-?[\d.]+$", r[1])}


def fed():
    up, lo = fred("DFEDTARU"), fred("DFEDTARL")
    return {"series": up, "rate_label": "Federal funds target range, upper bound",
            "extra": {"lower_bound": max(lo.items())} if lo else {},
            "source": "Board of Governors of the Federal Reserve System via FRED (DFEDTARU, DFEDTARL)",
            "source_url": "https://fred.stlouisfed.org/series/DFEDTARU"}


def boe():
    url = ("https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom="
           f"{(TODAY - dt.timedelta(days=760)).strftime('%d/%b/%Y')}&Dateto=now&SeriesCodes=IUDBEDR&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N")
    s = {}
    for r in csv.reader(io.StringIO(get(url))):
        if len(r) > 1 and re.match(r"^-?[\d.]+$", r[1].strip()):
            try:
                s[dt.datetime.strptime(r[0].strip(), "%d %b %Y").date().isoformat()] = f2(r[1])
            except ValueError:
                pass
    if not s:
        raise RuntimeError("no rows (IADB)")
    return {"series": s, "rate_label": "Bank Rate", "source": "Bank of England database (IUDBEDR, official Bank Rate)",
            "source_url": "https://www.bankofengland.co.uk/monetary-policy/the-interest-rate-bank-rate"}


def boc():
    d = json.loads(get("https://www.bankofcanada.ca/valet/observations/V39079/json?recent=500"))
    s = {o["d"]: f2(o["V39079"]["v"]) for o in d["observations"] if o.get("V39079", {}).get("v")}
    return {"series": s, "rate_label": "Target for the overnight rate", "source": "Bank of Canada Valet API (V39079)",
            "source_url": "https://www.bankofcanada.ca/rates/interest-rates/canadian-interest-rates/"}


def snb():
    s = {}
    for r in csv.reader(io.StringIO(get("https://data.snb.ch/api/cube/snbgwdzid/data/csv/en")), delimiter=";"):
        if len(r) == 3 and r[1] == "LZ" and r[2].strip() and r[0] >= (TODAY - dt.timedelta(days=760)).isoformat():
            s[r[0]] = f2(r[2])
    if not s:
        raise RuntimeError("no LZ rows")
    return {"series": s, "rate_label": "SNB policy rate", "source": "Swiss National Bank data portal (snbgwdzid, SNB policy rate)",
            "source_url": "https://data.snb.ch/en/topics/ziredev/cube/snbgwdzid"}


OFFICIAL = {"EMU": ecb, "USA": fed, "GBR": boe, "CAN": boc, "CHE": snb}

# Official press-release feeds; only items whose title matches the pattern are kept (monetary policy decisions).
RSS = {
    "EMU": ("https://www.ecb.europa.eu/rss/press.html", r"monetary policy decision"),
    "USA": ("https://www.federalreserve.gov/feeds/press_monetary.xml", r"FOMC statement|federal funds|issues FOMC"),
    "GBR": ("https://www.bankofengland.co.uk/rss/news", r"Bank Rate|Monetary Policy Summary"),
    "CAN": ("https://www.bankofcanada.ca/content_type/press-releases/feed/", r"policy rate"),
    "JPN": ("https://www.boj.or.jp/en/rss/whatsnew.xml", r"Statement on Monetary Policy"),
}


def rss_latest(url, pat):
    xml = get(url)
    items = re.findall(r"<item\b.*?</item>|<entry\b.*?</entry>", xml, re.S)
    for it in items:
        t = re.search(r"<title[^>]*>(.*?)</title>", it, re.S)
        title = unescape(re.sub(r"<!\[CDATA\[|\]\]>|<[^>]+>", "", t.group(1))).strip() if t else ""
        if not re.search(pat, title, re.I):
            continue
        l = re.search(r"<link[^>]*>(.*?)</link>", it, re.S) or re.search(r"<link[^>]*href=\"([^\"]+)\"", it)
        link = unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", l.group(1))).strip() if l else ""
        d = re.search(r"<(?:pubDate|dc:date|updated|published)>(.*?)</", it, re.S)
        date = None
        if d:
            raw = d.group(1).strip()
            for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
                try:
                    date = dt.datetime.strptime(raw.replace("GMT", "+0000") if "%z" in fmt else raw, fmt).date().isoformat()
                    break
                except ValueError:
                    continue
        # links must point to the bank's own site
        host = re.match(r"https://([^/]+)/", url).group(1).split(".", 1)[-1]
        if link and host not in link:
            link = ""
        return {"title": title[:200], "link": link, "date": date}
    return None


def last_change(series):
    ds = sorted(series)
    lc = None
    for a, b in zip(ds, ds[1:]):
        if abs(series[a] - series[b]) > 1e-9:
            lc = {"date": b, "from": series[a], "to": series[b]}
    return lc


def decisions(series, meetings):
    """Outcome of past meetings from the daily series: rate before the meeting vs 10 days after."""
    out = []
    ds = sorted(series)
    if not ds:
        return out
    for m in meetings:
        if m > TODAY.isoformat() or m < ds[0]:
            continue
        before = [d for d in ds if d < m]
        after_lim = (dt.date.fromisoformat(m) + dt.timedelta(days=10)).isoformat()
        after = [d for d in ds if m <= d <= after_lim]
        if not before:
            continue
        b = series[before[-1]]
        if not after or after[-1] < min(after_lim, ds[-1]):
            out.append({"date": m, "before": b, "after": None, "outcome": "pending data"})
            continue
        a = series[after[-1]]
        bp = round((a - b) * 100)
        out.append({"date": m, "before": b, "after": a, "change_bp": bp,
                    "outcome": "hold" if bp == 0 else ("hike" if bp > 0 else "cut")})
    return out


def main():
    try:
        cal = json.load(open("data/stats/cb_calendar.json", encoding="utf-8"))["banks"]
    except Exception as ex:  # noqa: BLE001
        print("cb: no calendar:", ex); return
    try:
        prev = json.load(open(OUT, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        prev = {"banks": {}}
    try:
        st = json.load(open("data/stats/latest.json", encoding="utf-8"))["series"]
    except Exception:  # noqa: BLE001
        st = {}
    cutoff = (TODAY - dt.timedelta(days=760)).isoformat()
    banks = {}
    for code, c in cal.items():
        b = {k: c.get(k) for k in ("bank", "country", "rate_name", "calendar_url", "announcement_time_local", "notes")}
        b["meetings"] = sorted(c.get("meetings", []))
        hist = dict(prev.get("banks", {}).get(code, {}).get("history", {}))
        fn = OFFICIAL.get(code)
        got = None
        if fn:
            try:
                got = fn()
            except Exception as ex:  # noqa: BLE001
                WARN.append(f"{code} official feed failed: {str(ex)[:120]}")
        if got and got["series"]:
            hist.update(got["series"])
            b.update(source=got["source"], source_url=got["source_url"], rate_label=got["rate_label"], feed="official")
            if got.get("extra"):
                b["other_rates"] = got["extra"]
        else:
            bis = st.get("EA20" if code == "EMU" else code, {}).get("policy_rate")
            if bis and bis.get("latest_daily"):
                d, v = bis["latest_daily"]
                hist[d] = v
                if bis.get("last_change"):
                    lc = bis["last_change"]
                    hist.setdefault(lc["date"], lc["to"])
                b.update(source="BIS central bank policy rates (WS_CBPOL), daily series", source_url="https://data.bis.org/topics/CBPOL",
                         rate_label=c.get("rate_name") or "Policy rate", feed="BIS (lags official announcements by up to ~1 week)")
            elif hist:
                b.update({k: prev["banks"][code].get(k) for k in ("source", "source_url", "rate_label")}, feed="previous run (sources failed today)")
        hist = {d: v for d, v in hist.items() if d >= cutoff}
        b["history"] = dict(sorted(hist.items()))
        if hist:
            d = max(hist)
            b["rate"], b["as_of"] = hist[d], d
            bis_lc = (st.get("EA20" if code == "EMU" else code, {}).get("policy_rate") or {}).get("last_change")
            lc = last_change(hist) if b.get("feed") == "official" else None
            lc = lc or bis_lc or last_change(hist) or prev.get("banks", {}).get(code, {}).get("last_change")
            b["last_change"] = lc
        today = TODAY.isoformat()
        b["next_meeting"] = next((m for m in b["meetings"] if m >= today), None)
        b["previous_meeting"] = next((m for m in reversed(b["meetings"]) if m < today), None)
        b["decisions"] = decisions(hist, b["meetings"])
        if code in RSS:
            try:
                b["latest_press_release"] = rss_latest(*RSS[code]) or prev.get("banks", {}).get(code, {}).get("latest_press_release")
            except Exception as ex:  # noqa: BLE001
                WARN.append(f"{code} RSS failed: {str(ex)[:100]}")
                b["latest_press_release"] = prev.get("banks", {}).get(code, {}).get("latest_press_release")
        banks[code] = b
    json.dump({"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "banks": banks},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    for code, b in banks.items():
        print(f"cb {code:4} {b.get('rate')!s:>6} as of {b.get('as_of')}  next {b.get('next_meeting')}  [{b.get('feed')}]")
    for w in WARN:
        print("warning:", w)


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:  # noqa: BLE001
        print("cb fetch failed:", ex); sys.exit(0)
