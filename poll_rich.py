#!/usr/bin/env python3
"""Watch the cpiX_* rich-stack exports (planting_dekad + WRSI/WSI stages) until they settle."""
import ee, time, argparse
from collections import defaultdict
ee.Initialize(project="ee-manzikye")

def snap():
    by = defaultdict(list); err = {}
    for o in ee.data.listOperations():
        m = o.get("metadata", {}); d = m.get("description", "")
        if not d.startswith("cpiX_"): continue
        by[m.get("state", "?")].append(d)
        if o.get("error"): err[d] = o["error"].get("message", "")
    return by, err

def show(by, err):
    order = ["RUNNING", "PENDING", "SUCCEEDED", "FAILED", "CANCELLED"]
    print(f"[{time.strftime('%H:%M:%S')}] " + " · ".join(f"{s}:{len(by.get(s,[]))}" for s in order if by.get(s)))
    for s in ("FAILED", "CANCELLED"):
        for d in sorted(by.get(s, [])): print(f"   !! {s}: {d}  {err.get(d,'')[:90]}")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--watch", type=int, default=0); a = ap.parse_args()
    while True:
        by, err = snap(); show(by, err)
        active = len(by.get("RUNNING", [])) + len(by.get("PENDING", []))
        if not a.watch or active == 0:
            print("all cpiX_ tasks settled." if active == 0 else ""); break
        time.sleep(a.watch)

if __name__ == "__main__":
    main()
