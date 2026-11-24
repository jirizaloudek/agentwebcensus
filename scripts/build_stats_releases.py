#!/usr/bin/env python3
"""Detect new official data releases: compare today's data/stats/latest.json with the version in git HEAD
(the previous daily run) and append every country x indicator whose latest reference period moved forward
to data/stats/releases.json (rolling 120 days). Run after fetch_indicators.py, before build_site.py.
Never fails the workflow."""
import datetime as dt, json, os, subprocess, sys

CUR = "data/stats/latest.json"
OUT = "data/stats/releases.json"
KEEP_DAYS = 120
SKIP = {"imf_gdp_growth", "imf_inflation", "population"}  # annual / forecast vintages, not releases


def latest_actual(s):
    obs = [o for o in s.get("obs", []) if o[1] is not None and not (len(o) > 2 and o[2])]
    return obs[-1] if obs else None, (obs[-2] if len(obs) > 1 else None)


def main():
    if not os.path.exists(CUR):
        return
    cur = json.load(open(CUR))
    try:
        prev = json.loads(subprocess.run(["git", "show", "HEAD:" + CUR], capture_output=True, text=True, check=True).stdout)
    except Exception as ex:  # noqa: BLE001
        print("no previous latest.json in HEAD:", ex)
        prev = None
    log = {"events": []}
    if os.path.exists(OUT):
        try:
            log = json.load(open(OUT))
        except Exception:  # noqa: BLE001
            pass
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    seen = {(x["iso3"], x["indicator"], x["period"]) for x in log["events"]}
    new = []
    if prev:
        for c, ser in cur["series"].items():
            for k, s in ser.items():
                if k in SKIP:
                    continue
                now, before = latest_actual(s)
                if not now:
                    continue
                p_old = latest_actual(prev["series"].get(c, {}).get(k, {}))[0] if prev["series"].get(c, {}).get(k) else None
                if p_old and str(now[0]) <= str(p_old[0]):
                    continue
                if (c, k, now[0]) in seen:
                    continue
                new.append({"detected": today, "iso3": c, "name": cur["countries"].get(c, {}).get("name", c), "indicator": k,
                            "period": now[0], "value": now[1], "previous_period": before[0] if before else None,
                            "previous_value": before[1] if before else None, "source": s.get("source_name") or s.get("source")})
    cutoff = (dt.date.fromisoformat(today) - dt.timedelta(days=KEEP_DAYS)).isoformat()
    ev = [x for x in log["events"] if x["detected"] >= cutoff] + new
    ev.sort(key=lambda x: (x["detected"], x["name"], x["indicator"]), reverse=True)
    json.dump({"updated": today, "note": "Detected by daily comparison of official series; 'detected' is the day datacensus.org first saw the new period, not the official release time.",
               "events": ev}, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    print(f"releases: {len(new)} new today, {len(ev)} in log")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:  # noqa: BLE001
        print("WARNING build_stats_releases failed:", repr(ex), file=sys.stderr)
