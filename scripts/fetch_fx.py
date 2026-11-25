#!/usr/bin/env python3
"""Fetch ECB euro foreign exchange reference rates (last 90 days, published ~16:00 CET on TARGET working days).
Output data/stats/fx.json {generated, base:"EUR", dates:[...], rates:{CUR:{date:rate}}}. Never fails the workflow."""
import json, re, sys, urllib.request, datetime as dt
URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
try:
    req = urllib.request.Request(URL, headers={"User-Agent": "agentwebcensus/1.0 (+https://agents.datacensus.org)"})
    xml = urllib.request.urlopen(req, timeout=60).read().decode()
    rates, dates = {}, []
    for m in re.finditer(r"<Cube time=['\"]([\d-]+)['\"]>(.*?)</Cube>(?=\s*(?:<Cube time|</Cube>))", xml, re.S):
        d = m.group(1); dates.append(d)
        for c, r in re.findall(r"currency=['\"](\w+)['\"] rate=['\"]([\d.]+)['\"]", m.group(2)):
            rates.setdefault(c, {})[d] = float(r)
    dates.sort()
    if len(dates) < 5 or "USD" not in rates: raise ValueError("too little data")
    json.dump({"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "base": "EUR", "dates": dates, "rates": rates,
               "source": "European Central Bank euro foreign exchange reference rates", "source_url": "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"},
              open("data/stats/fx.json", "w"), separators=(",", ":"))
    print("fx:", len(rates), "currencies,", len(dates), "days, latest", dates[-1])
except Exception as ex:  # noqa: BLE001
    print("fx fetch failed:", ex); sys.exit(0)
