"""Admin-level risk layers for the atlas from the 2024 risk monitor (risk_app.html):
crop-failure risk (ASAP classes, all 8 countries with a 2024 run) and HarvestStat-calibrated maize yield
(Kenya wards, Ethiopia woredas). Units with < 1 % maize area are grey (no colour from a handful of pixels)."""
import os, re, json, numpy as np
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import Polygon, MultiPolygon
from PIL import Image
from matplotlib.colors import LinearSegmentedColormap
H0 = os.path.dirname(os.path.abspath(__file__))
g = json.load(open(os.path.join(H0, "layers", "grid.json")))
W, H = g["size"]; (S_, W_), (N_, E_) = g["bounds"]; TR = from_origin(W_, N_, g["res_deg"], g["res_deg"])
s = open(os.path.expanduser("~/Downloads/planting_pipeline/risk_app.html")).read()
m = re.search(r'<script[^>]*type="application/json"[^>]*>', s); st = m.end(); D = json.loads(s[st:s.index("</script>", st)])
P = {p["id"]: p for p in D["products"]}
# painting order: later overrides earlier (Tanzania: Msimu over Masika)
PRODS = [("ke_long", "KEN"), ("et_meher", "ETH"), ("ug_1st", "UGA"), ("tz_mas", "TZA"), ("tz_msi", "TZA"),
         ("rw_a", "RWA"), ("bi_a", "BDI"), ("so_gu", "SOM"), ("ss_main", "SSD")]
import pandas as pd
_cal = pd.read_csv(os.path.expanduser("~/Downloads/planting_pipeline/Cropyield-Data/ym_calibration_local.csv")).set_index("file")
CAL = {"ke_long": float(_cal.loc["app:ke_long", "ym_cal"]), "et_meher": float(_cal.loc["app:et_meher", "ym_cal"])}   # typical-year Ym
MIN_CAF = 0.01
MIN_CAF_BY = {"so_gu": 0.001, "ss_main": 0.001}   # Somalia, South Sudan: maize < 1 % of nearly every district
fail = np.zeros((H, W), "uint8"); yld = np.zeros((H, W), "float32"); cover = np.zeros((H, W), "uint8")
summ = {}
def geom(u):
    return MultiPolygon([Polygon(r) for r in u["g"] if len(r) >= 4])
for pid, i3 in PRODS:
    p = P[pid]; lv = max(p["levels"], key=int); units = p["levels"][lv]["units"]
    shapes_all = [(geom(u), 1) for u in units]
    cover |= rasterize(shapes_all, out_shape=(H, W), transform=TR).astype("uint8")
    thr = MIN_CAF_BY.get(pid, MIN_CAF)
    ok = [u for u in units if u["a"].get("fail") is not None and (u["a"].get("caf") or 0) >= thr]
    cls = lambda v: 1 + (v >= 25) + (v >= 50) + (v >= 75)
    if ok:
        f = rasterize([(geom(u), cls(u["a"]["fail"])) for u in ok], out_shape=(H, W), transform=TR).astype("uint8")
        fail = np.where(f > 0, f, fail)
    if pid in CAL:
        yy = [(u, u["a"]["cpi"] / 100 * CAL[pid]) for u in units if u["a"].get("cpi") is not None and (u["a"].get("caf") or 0) >= MIN_CAF]
        y = rasterize([(geom(u), v) for u, v in yy], out_shape=(H, W), transform=TR, dtype="float32")
        yld = np.where(y > 0, y, yld)
    lab = p["levels"][lv]["label"] if "label" in p["levels"][lv] else "units"
    vals = [u["a"]["fail"] for u in ok]
    e = summ.setdefault(i3, {"seasons": [], "units": 0, "watch": 0, "alert": 0, "critical": 0, "level": lab, "min_caf_pct": thr * 100})
    e["seasons"].append(p["season"]); e["units"] += len(ok)
    e["watch"] += sum(25 <= v < 50 for v in vals); e["alert"] += sum(50 <= v < 75 for v in vals); e["critical"] += sum(v >= 75 for v in vals)
    if pid in CAL:
        ys = sorted(v for _, v in yy); e["yield_median"] = round(ys[len(ys) // 2], 2)
        c = _cal.loc["app:" + pid]
        e["yield_note"] = (f"Typical-year calibration: ceiling {c.ym_cal} t/ha fitted to HarvestStat {c.season} {c.years} "
                           f"({c.n_units} units; held-out error {c.test_mae_cal} t/ha vs {c.test_mae_default} uncalibrated; r {c.r_pred_obs}).")
    cp = sorted(u["a"]["cpi"] for u in units if u["a"].get("cpi") is not None and (u["a"].get("caf") or 0) >= thr)
    if cp: e["cpi_median"] = round(cp[len(cp) // 2])
# PNGs: grey where a reporting unit exists but has < 1 % maize or no value
GREY = (170, 172, 165, 150)
lut = np.array([(0, 0, 0, 0), (26, 152, 80, 255), (254, 224, 139, 255), (244, 109, 67, 255), (165, 0, 38, 255)], "uint8")
rgba = lut[fail]; rgba[(fail == 0) & (cover > 0)] = GREY
Image.fromarray(rgba, "RGBA").save(os.path.join(H0, "layers", "risk_fail.png"), optimize=True)
cm = LinearSegmentedColormap.from_list("y", ["#f7fcb9", "#78c679", "#005a32"])
t = np.clip(yld / 4.0, 0, 1); rg = (cm(t) * 255).astype("uint8"); rg[..., 3] = np.where(yld > 0, 255, 0)
kecov = rasterize([(geom(u), 1) for pid in CAL for u in P[pid]["levels"][max(P[pid]["levels"], key=int)]["units"]], out_shape=(H, W), transform=TR)
rg[(yld <= 0) & (kecov > 0)] = GREY
Image.fromarray(rg, "RGBA").save(os.path.join(H0, "layers", "risk_yield.png"), optimize=True)
json.dump(summ, open(os.path.join(H0, "risk_summary.json"), "w"), indent=1)
for k, v in summ.items(): print(k, v)
