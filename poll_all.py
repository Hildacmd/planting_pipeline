#!/usr/bin/env python3
"""Watch BOTH cpi_ and cpiX_ 2024 exports until all settle. Reports per-prefix state and flags failures."""
import ee, time, argparse
from collections import defaultdict
ee.Initialize(project="ee-manzikye")

def snap():
    by = defaultdict(lambda: defaultdict(list)); err = {}
    for o in ee.data.listOperations():
        m = o.get("metadata", {}); d = m.get("description", "")
        pfx = "cpiX_" if d.startswith("cpiX_") else ("cpi_" if d.startswith("cpi_") else None)
        if not pfx: continue
        by[pfx][m.get("state", "?")].append(d)
        if o.get("error"): err[d] = o["error"].get("message", "")
    return by, err

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--watch", type=int, default=300); a = ap.parse_args()
    order = ["RUNNING", "PENDING", "SUCCEEDED", "FAILED", "CANCELLED"]
    while True:
        by, err = snap(); active = 0
        line = []
        for pfx in ("cpi_", "cpiX_"):
            b = by[pfx]; active += len(b.get("RUNNING", [])) + len(b.get("PENDING", []))
            line.append(f"{pfx} " + " ".join(f"{s}:{len(b.get(s,[]))}" for s in order if b.get(s)))
        print(f"[{time.strftime('%H:%M:%S')}] " + "  |  ".join(line))
        for pfx in ("cpi_", "cpiX_"):
            for d in sorted(set(by[pfx].get("FAILED", []))):
                print(f"   !! FAILED {d}  {err.get(d,'')[:80]}")
        if not a.watch or active == 0:
            print("all cpi_/cpiX_ tasks settled." if active == 0 else ""); break
        time.sleep(a.watch)

if __name__ == "__main__":
    main()
