#!/usr/bin/env python3
"""Fetch the latest official macro indicators per country (OECD, BIS, IMF, World Bank, Eurostat).

Writes data/stats/latest.json (compact JSON, ISO3 keys). Standard library only.
Robust by design: every source is wrapped in try/except (60 s timeout, 2 retries); when a
source fails, the series from the previous latest.json are kept. Never crashes, never
overwrites a good file with an empty one.
"""
import csv
import datetime as dt
import io
import json
import os
import statistics
import sys
import time
import urllib.parse
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "stats", "latest.json")
TIMEOUT = 60
RETRIES = 2
MAX_OBS = 60
UA = "agentwebcensus-indicators/1.0 (+https://agents.datacensus.org; AI-generated open data)"

NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date()
YEAR = TODAY.year

OECD = "https://sdmx.oecd.org/public/rest/data/"
OECD_AGG = {"EA": "EA20", "EA20": "EA20", "EA21": "EA20", "EU": "EU27", "EU27": "EU27",
            "EU27_2020": "EU27", "OECD": "OECD"}
AGG_NAMES = {"EA20": "Euro area", "EU27": "European Union (27 countries)", "OECD": "OECD total"}

INDICATORS = {
    "inflation": {"name": "Inflation rate (CPI, % change over 12 months)", "unit": "%", "freq": "monthly"},
    "inflation_hicp": {"name": "Inflation rate (HICP, annual rate of change, Eurostat)", "unit": "%", "freq": "monthly"},
    "unemployment": {"name": "Unemployment rate (% of labour force, seasonally adjusted, ages 15+)", "unit": "%", "freq": "monthly"},
    "gdp_growth": {"name": "Real GDP growth (% change vs same quarter a year earlier)", "unit": "%", "freq": "quarterly"},
    "gdp_growth_qoq": {"name": "Real GDP growth (% change vs previous quarter)", "unit": "%", "freq": "quarterly"},
    "policy_rate": {"name": "Central bank policy rate (% per year)", "unit": "%", "freq": "monthly (month-end) + latest daily"},
    "imf_gdp_growth": {"name": "Real GDP growth, annual % (IMF World Economic Outlook, incl. forecasts)", "unit": "%", "freq": "annual"},
    "imf_inflation": {"name": "Inflation, average consumer prices, annual % (IMF World Economic Outlook, incl. forecasts)", "unit": "%", "freq": "annual"},
    "population": {"name": "Population, total (World Bank, latest available year)", "unit": "persons", "freq": "annual"},
}

FAILED = []
WARN = []


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def http_get(url, binary=False):
    last = None
    for attempt in range(RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = r.read()
            return data if binary else data.decode("utf-8-sig")
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < RETRIES:
                time.sleep(2 + 3 * attempt)
    raise RuntimeError(f"GET failed {url[:120]}: {last}")


def rnd(v):
    return round(float(v), 2)


def months_back(n):
    y, m = TODAY.year, TODAY.month - n
    while m < 1:
        m += 12
        y -= 1
    return f"{y:04d}-{m:02d}"


def quarters_back(n):
    q = (TODAY.month - 1) // 3
    y = TODAY.year
    q -= n
    while q < 0:
        q += 4
        y -= 1
    return f"{y}-Q{q + 1}"


def mk(source, source_name, url, obs, updated=None, **extra):
    s = {"source": source, "source_name": source_name, "source_url": url,
         "obs": obs[-MAX_OBS:]}
    if updated:
        s["last_updated_by_source"] = updated
    s.update(extra)
    s["fetched"] = TODAY.isoformat()
    return s


# ---------------------------------------------------------------- World Bank
def fetch_worldbank():
    """Returns (countries_meta{iso3: {name, iso2, region}}, population{iso3: series})."""
    meta = {}
    raw = json.loads(http_get("https://api.worldbank.org/v2/country?format=json&per_page=400"))
    for c in raw[1]:
        region = (c.get("region") or {}).get("id")
        if not region or region == "NA":
            continue
        meta[c["id"]] = {"name": c["name"], "iso2": c.get("iso2Code", ""),
                         "region": c["region"]["value"].strip()}
    url = "https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL?format=json&mrnev=1&per_page=400"
    raw = json.loads(http_get(url))
    updated = raw[0].get("lastupdated")
    pop = {}
    for r in raw[1] or []:
        iso3 = r.get("countryiso3code") or ""
        if iso3 in meta and r.get("value") is not None:
            pop[iso3] = mk("World Bank", "World Bank WDI SP.POP.TOTL",
                           "https://data.worldbank.org/indicator/SP.POP.TOTL?locations=" + meta[iso3]["iso2"],
                           [[str(r["date"]), int(r["value"])]], updated)
    return meta, pop


# ---------------------------------------------------------------------- OECD
def oecd_csv(path):
    url = OECD + path + ("&" if "?" in path else "?") + "format=csvfilewithlabels"
    return list(csv.DictReader(io.StringIO(http_get(url)))), url.replace("&format=csvfilewithlabels", "")


def oecd_collect(rows, valid, names, extra_filter=None):
    """rows -> {iso3: {tag: {period: value}}}; unknown names stored in `names`."""
    out = {}
    for r in rows:
        if extra_filter and not extra_filter(r):
            continue
        area = r["REF_AREA"]
        key = OECD_AGG.get(area, area)
        if key not in valid and key not in AGG_NAMES:
            continue
        if r["OBS_VALUE"] == "":
            continue
        names.setdefault(key, r.get("Reference area") or key)
        out.setdefault(key, {}).setdefault(r.get("TRANSFORMATION", ""), {})[r["TIME_PERIOD"]] = r["OBS_VALUE"]
    return out


def fetch_oecd_inflation(valid, names):
    key = ".M.N.CPI.PA._T.N.GY"
    path = f"OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/{key}?startPeriod={months_back(37)}"
    rows, url = oecd_csv(path)
    data = oecd_collect(rows, valid, names)
    return {k: mk("OECD", "OECD Prices database (DF_PRICES_ALL)", url,
                  [[p, rnd(v)] for p, v in sorted(t["GY"].items())]) for k, t in data.items() if t.get("GY")}


def fetch_oecd_unemployment(valid, names):
    key = ".UNE_LF_M.PT_LF_SUB._Z.Y._T.Y_GE15._Z.M"
    path = f"OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,1.0/{key}?startPeriod={months_back(37)}"
    rows, url = oecd_csv(path)
    data = oecd_collect(rows, valid, names)
    return {k: mk("OECD", "OECD Labour Force Statistics, monthly unemployment rates (DF_IALFS_UNE_M)", url,
                  [[p, rnd(v)] for p, v in sorted((t.get("_Z") or t.get("")).items())]) for k, t in data.items() if t.get("_Z") or t.get("")}


def fetch_oecd_gdp(valid, names):
    key = "Q.Y..S1.S1.B1GQ._Z._Z._Z.PC.L.GY+G1.T0102"
    path = ("OECD.SDD.NAD,DSD_NAMAIN1@DF_QNA_EXPENDITURE_GROWTH_OECD,1.1/"
            f"{key}?startPeriod={quarters_back(14)}")
    rows, url = oecd_csv(path)
    data = oecd_collect(rows, valid, names)
    sn = "OECD Quarterly National Accounts, GDP growth (DF_QNA_EXPENDITURE_GROWTH_OECD)"
    yoy, qoq = {}, {}
    for k, t in data.items():
        if t.get("GY"):
            yoy[k] = mk("OECD", sn, url, [[p, rnd(v)] for p, v in sorted(t["GY"].items())])
        if t.get("G1"):
            qoq[k] = mk("OECD", sn, url, [[p, rnd(v)] for p, v in sorted(t["G1"].items())])
    return yoy, qoq


# ----------------------------------------------------------------------- BIS
def fetch_bis(valid, names):
    url = "https://data.bis.org/static/bulk/WS_CBPOL_csv_flat.zip"
    z = zipfile.ZipFile(io.BytesIO(http_get(url, binary=True)))
    f = io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8-sig", newline="")
    monthly, daily = {}, {}
    cutoff_m = months_back(40)
    cutoff_d = (TODAY - dt.timedelta(days=3 * 365)).isoformat()
    for r in csv.DictReader(f):
        fr = r["FREQ:Frequency"].split(":")[0].strip()
        code, _, label = r["REF_AREA:Reference area"].partition(":")
        code, label = code.strip(), label.strip()
        iso2 = code
        t = r["TIME_PERIOD:Time period or range"]
        v = (r.get("OBS_VALUE") if "OBS_VALUE" in r else r.get("OBS_VALUE:Observation Value", "")) or ""
        v = v.split(":")[0].strip()
        if v == "" or v.upper() == "NAN":
            continue
        if fr == "M" and t >= cutoff_m:
            monthly.setdefault(iso2, {})[t] = float(v)
        elif fr == "D":
            daily.setdefault(iso2, {})[t] = float(v)
        names.setdefault("bis:" + iso2, label)
    out = {}
    for iso2, m in monthly.items():
        d = daily.get(iso2, {})
        latest_m = max(m)
        latest_d = max(d) if d else None
        newest = max(latest_m, (latest_d or "")[:7])
        if newest < months_back(24):  # discontinued (e.g. old national euro-area members)
            continue
        iso3 = "EA20" if iso2 == "XM" else valid.get(iso2)
        if not iso3:
            continue
        obs = [[p, rnd(v)] for p, v in sorted(m.items())][-36:]
        extra = {}
        if d:
            dates = sorted(d)
            extra["latest_daily"] = [dates[-1], rnd(d[dates[-1]])]
            lc = None
            for prev, cur in zip(dates, dates[1:]):
                if abs(d[cur] - d[prev]) > 1e-9:
                    lc = (cur, d[prev], d[cur])
            if lc:
                extra["last_change"] = {"date": lc[0], "from": rnd(lc[1]), "to": rnd(lc[2])}
            else:
                extra["last_change"] = None
                extra["last_change_note"] = f"no change since {dates[0]} (start of daily window used)"
        out[iso3] = mk("BIS", "BIS central bank policy rates (WS_CBPOL)",
                       "https://data.bis.org/topics/CBPOL", obs, **extra)
    return out


# ------------------------------------------------------------------------ IMF
def fetch_imf(code, valid):
    raw = json.loads(http_get(f"https://www.imf.org/external/datamapper/api/v1/{code}"))
    vals = raw["values"][code]
    out = {}
    for c, years in vals.items():
        iso3 = {"UVK": "XKX"}.get(c, c)
        if iso3 not in valid:
            continue
        obs = []
        for y in range(YEAR - 5, YEAR + 2):
            v = years.get(str(y))
            if v is not None:
                obs.append([str(y), rnd(v), y >= YEAR])
        if obs:
            out[iso3] = mk("IMF", "IMF World Economic Outlook (DataMapper " + code + ")",
                           f"https://www.imf.org/external/datamapper/{code}@WEO", obs,
                           note=f"IMF WEO; values for {YEAR} and later are forecasts (third element true); "
                                f"{YEAR - 1} may still be an estimate")
    return out


# ------------------------------------------------------------------- Eurostat
def jsonstat_series(d):
    ids, sizes = d["id"], d["size"]
    cats = {i: list(d["dimension"][i]["category"]["index"].items()) for i in ids}
    # category index may be dict {code: pos}; sort by pos
    cats = {i: [c for c, _ in sorted(v, key=lambda x: x[1])] for i, v in cats.items()}
    strides, s = {}, 1
    for i, n in reversed(list(zip(ids, sizes))):
        strides[i] = s
        s *= n
    geo_i, time_i = ids.index("geo"), ids.index("time")
    out = {}
    for pos, v in d["value"].items():
        pos = int(pos)
        g = cats["geo"][(pos // strides["geo"]) % sizes[geo_i]]
        t = cats["time"][(pos // strides["time"]) % sizes[time_i]]
        out.setdefault(g, {})[t] = v
    return out


def fetch_eurostat(iso2_to_iso3):
    since = months_back(36)
    base = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    cands = [("prc_hicp_manr", f"?coicop=CP00&sinceTimePeriod={since}"),
             ("prc_hicp_minr", f"?coicop18=TOTAL&unit=RCH_A&sinceTimePeriod={since}")]
    stale_cut = months_back(3)
    best = None
    errs = []
    for code, q in cands:
        try:
            d = json.loads(http_get(base + code + q))
            if "error" in d:
                raise RuntimeError(str(d["error"])[:150])
            ser = jsonstat_series(d)
            latest = max((max(t) for t in ser.values() if t), default="")
            if latest >= stale_cut:
                best = (code, d, ser)
                break
            WARN.append(f"Eurostat {code} stale (latest {latest}), trying next dataset")
        except Exception as e:  # noqa: BLE001
            errs.append(f"{code}: {e}")
    if not best:
        raise RuntimeError("no fresh Eurostat HICP dataset; " + "; ".join(errs))
    code, d, ser = best
    out, names = {}, {}
    upd = d.get("updated")
    for g, t in ser.items():
        if g in ("EA", "EA19", "EA20", "EA21", "EA22"):
            key = "EA20"
            if g != "EA" and "EA" in ser:
                continue
            if g not in ("EA",) and key in out:
                continue
        elif g in ("EU", "EU27_2020"):
            key = "EU27"
            if g == "EU" and "EU27_2020" in ser:
                continue
        else:
            key = iso2_to_iso3.get({"EL": "GR", "UK": "GB"}.get(g, g))
            if not key:
                continue
        obs = [[p, rnd(v)] for p, v in sorted(t.items()) if v is not None]
        if obs:
            out[key] = mk("Eurostat", f"Eurostat HICP, annual rate of change ({code})",
                          f"https://ec.europa.eu/eurostat/databrowser/view/{code}/default/table", obs, upd)
    return out


# -------------------------------------------------------------------- driver
def load_previous():
    try:
        with open(OUT, encoding="utf-8") as f:
            p = json.load(f)
        if p.get("series"):
            return p
    except Exception:  # noqa: BLE001
        pass
    return None


def main():
    t0 = time.time()
    prev = load_previous()
    new = {}  # indicator -> {iso3: series}
    names = {}
    meta = {}

    def run(label, indicators, fn):
        try:
            res = fn()
            if not isinstance(res, tuple):
                res = (res,)
            for ind, data in zip(indicators, res):
                if not data:
                    raise RuntimeError(f"empty result for {ind}")
                new[ind] = data
        except Exception as e:  # noqa: BLE001
            FAILED.append(label)
            log(f"WARNING: source {label} failed: {e}")

    # World Bank first (country list drives the filtering)
    try:
        meta, pop = fetch_worldbank()
        new["population"] = pop
    except Exception as e:  # noqa: BLE001
        FAILED.append("worldbank")
        log(f"WARNING: source worldbank failed: {e}")
    if not meta and prev:
        meta = {k: v for k, v in prev["countries"].items() if k not in AGG_NAMES}
    valid_iso3 = set(meta)
    iso2_to_iso3 = {v["iso2"]: k for k, v in meta.items() if v.get("iso2")}
    valid_for_oecd = valid_iso3

    run("oecd_inflation", ["inflation"], lambda: fetch_oecd_inflation(valid_for_oecd, names))
    run("oecd_unemployment", ["unemployment"], lambda: fetch_oecd_unemployment(valid_for_oecd, names))
    run("oecd_gdp", ["gdp_growth", "gdp_growth_qoq"], lambda: fetch_oecd_gdp(valid_for_oecd, names))
    run("bis_policy_rate", ["policy_rate"], lambda: fetch_bis(iso2_to_iso3, names))
    run("imf_gdp_growth", ["imf_gdp_growth"], lambda: fetch_imf("NGDP_RPCH", valid_iso3))
    run("imf_inflation", ["imf_inflation"], lambda: fetch_imf("PCPIPCH", valid_iso3))
    run("eurostat_hicp", ["inflation_hicp"], lambda: fetch_eurostat(iso2_to_iso3))

    # Fallback: HICP fills EU countries missing from OECD CPI (BG, HR, CY, MT, RO ...)
    if "inflation_hicp" in new:
        infl = new.setdefault("inflation", {})
        for iso3, s in new["inflation_hicp"].items():
            if not (iso3 in valid_iso3 or iso3 in AGG_NAMES) or not s.get("obs"):
                continue
            cur = infl.get(iso3)
            if cur is None:
                fb = dict(s)
                fb["note"] = "fallback: Eurostat HICP (country missing from OECD CPI)"
                infl[iso3] = fb
            elif cur.get("obs") and s["obs"][-1][0] > cur["obs"][-1][0]:
                fb = dict(s)
                fb["note"] = (f"Eurostat HICP used: newer than OECD CPI (OECD latest {cur['obs'][-1][0]}, "
                              f"Eurostat latest {s['obs'][-1][0]})")
                infl[iso3] = fb
    # Euro area members share the ECB policy rate (BIS publishes it once, as the euro area)
    EURO = ["AUT", "BEL", "BGR", "HRV", "CYP", "EST", "FIN", "FRA", "DEU", "GRC", "IRL", "ITA", "LVA", "LTU",
            "LUX", "MLT", "NLD", "PRT", "SVK", "SVN", "ESP"]
    pr = new.get("policy_rate", {})
    if "EA20" in pr:
        for iso3 in EURO:
            if iso3 not in pr and iso3 in valid_iso3:
                s_ = dict(pr["EA20"])
                s_["note"] = "euro area member: ECB policy rate (BIS euro area series)"
                pr[iso3] = s_
    # Drop monthly series whose latest observation is too old to be called "latest"
    stale_cut = months_back(9)
    for ind in ("inflation", "inflation_hicp", "unemployment", "policy_rate"):
        for iso3 in [c for c, s in new.get(ind, {}).items() if not s.get("obs") or s["obs"][-1][0] < stale_cut]:
            WARN.append(f"dropped stale {ind} for {iso3} (latest {new[ind][iso3]['obs'][-1][0] if new[ind][iso3].get('obs') else 'none'})")
            del new[ind][iso3]

    # Keep previous series for failed sources / missing indicators
    if prev:
        for ind in INDICATORS:
            if ind not in new:
                kept = {c: s[ind] for c, s in prev["series"].items() if ind in s}
                if kept:
                    new[ind] = kept
                    WARN.append(f"kept previous '{ind}' series for {len(kept)} countries")
        for c, m in prev.get("countries", {}).items():
            meta.setdefault(c, m)

    series = {}
    for ind, data in new.items():
        for c, s in data.items():
            series.setdefault(c, {})[ind] = s
    if not series:
        log("ERROR: no data at all; leaving existing file untouched")
        print("failed sources:", FAILED)
        return 0

    countries = {}
    for c in sorted(series):
        if c in meta:
            m = dict(meta[c])
        elif c in AGG_NAMES:
            m = {"name": AGG_NAMES[c], "iso2": "", "region": "Aggregate"}
        else:
            m = {"name": names.get(c, c), "iso2": "", "region": ""}
        countries[c] = m

    out = {"generated": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "indicators": INDICATORS, "countries": countries,
           "series": {c: series[c] for c in sorted(series)}}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT)

    # summary
    print(f"wrote {OUT} ({os.path.getsize(OUT) / 1024:.0f} kB), {len(series)} countries/aggregates")
    for ind in INDICATORS:
        lat = sorted(s[ind]["obs"][-1][0] for s in series.values() if ind in s and s[ind]["obs"])
        if lat:
            print(f"  {ind:16s} countries={len(lat):3d} latest max={lat[-1]} median={lat[len(lat) // 2]}")
        else:
            print(f"  {ind:16s} none")
    for w in WARN:
        print("warning:", w)
    print("failed sources:", FAILED or "none")
    print(f"runtime: {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        log(f"WARNING: unexpected error, existing data left untouched: {e!r}")
        sys.exit(0)
