#!/usr/bin/env python3
"""Planting-window PDF map report (GEE getThumbURL -> reportlab).

For each viable (country x crop x season) product this renders styled maps server-side
(lightweight thumbnails, no heavy GeoTIFF export) and lays them into a PDF:
  1. Planting dekad        (per-pixel estimated planting date)
  2. WRSI + performance     (water requirement satisfaction; skipped with --no-wrsi)
  3. Skill vs FEWS/FAO cal   (estimate inside vs outside the calendar window)
  4. Signal strength         (green-up amplitude / detection confidence)

Each layer is rendered independently and failures are non-fatal (the page notes the miss),
so a throttled WRSI layer won't sink the whole report.

Run:
  EE_PROJECT=your-project python generate_planting_report.py --year 2024 --country Kenya --crop maize
  EE_PROJECT=your-project python generate_planting_report.py --year 2024 --country Kenya --crop maize --no-wrsi
"""
import argparse, sys, os, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from src import utils, s2_preprocess as S2, s1_preprocess as S1
from src import fusion_phenometrics as FZ, planting_date as PD, wrsi_feedback as WR
from src import zonal_aggregate as ZA, soil as SOIL, skill_stats as SK

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.colors import HexColor
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image as RLImage, PageBreak)
from PIL import Image as PILImage

GAUL_NAME = {
 "Ethiopia":"Ethiopia","Kenya":"Kenya","Uganda":"Uganda","Tanzania":"United Republic of Tanzania",
 "Rwanda":"Rwanda","Burundi":"Burundi","South_Sudan":"South Sudan","Sudan":"Sudan",
 "Somalia":"Somalia","Eritrea":"Eritrea","Djibouti":"Djibouti"}

# palettes
PAL_DEKAD  = ['#2b83ba', '#abdda4', '#ffffbf', '#fdae61', '#d7191c']   # early -> late
PAL_WRSI   = ['#d7191c', '#fdae61', '#ffffbf', '#a6d96a', '#1a9641']   # poor -> good
PAL_HIT    = ['#d7191c', '#1a9641']                                    # miss / hit
PAL_AMP    = ['#440154', '#3b528b', '#21918c', '#5ec962', '#fde725']   # low -> high signal

DARK = HexColor("#1a3a5c"); MED = HexColor("#2d6a9f"); GREY = HexColor("#f4f6f8")


def crop_mask_image(ee, crop, mask_asset):
    if mask_asset:
        return ee.Image(mask_asset).selfMask()
    wc = ee.ImageCollection("ESA/WorldCereal/2021/MODELS/v100")
    prod = "maize" if crop == "maize" else "temporarycrops"
    return wc.filter(ee.Filter.eq("product", prod)).mosaic().select("classification").eq(100).selfMask()


def thumb(ee, styled_rgb, region, out_path, dimensions=1100):
    """Download a rendered PNG thumbnail of an already-visualized (RGB) image."""
    url = styled_rgb.getThumbURL({"region": region, "dimensions": dimensions, "format": "png"})
    urllib.request.urlretrieve(url, out_path)
    return out_path


def styled(ee, img, vis, boundary_fc):
    """Visualize img with vis params and draw the country boundary on top."""
    base = img.visualize(**vis)
    outline = ee.Image().byte().paint(boundary_fc, 1, 1).visualize(palette=["333333"])
    return base.blend(outline)


def fit(path, max_w, max_h):
    im = PILImage.open(path); r = im.size[0] / im.size[1]
    w, h = (max_w, max_w / r) if (max_w / r) <= max_h else (max_h * r, max_h)
    return RLImage(path, width=w, height=h)


def legend_table(rows, S):
    """rows: list of (swatch_hexlist_or_hex, label). Simple 2-col legend."""
    data = []
    for sw, lab in rows:
        data.append([Paragraph(f'<font color="{sw}">■</font>', S["leg"]),
                     Paragraph(lab, S["leg"])])
    t = Table(data, colWidths=[0.8 * cm, 15 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 1),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--country"); ap.add_argument("--crop")
    ap.add_argument("--mask-asset", default=None)
    ap.add_argument("--orbit", default="DESCENDING")
    ap.add_argument("--calendar", default="config/season_calendar.csv")
    ap.add_argument("--no-wrsi", action="store_true")
    ap.add_argument("--maps-dir", default="planting_maps")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    ee = utils.gee_init()
    kc_cfg, soil_cfg = utils.load_crop_coeffs()
    rows = list(utils.viable_products(utils.load_calendar(args.calendar)))
    if args.country: rows = [r for r in rows if r["country"] == args.country]
    if args.crop:    rows = [r for r in rows if r["crop"].lower() == args.crop.lower()]
    if not rows:
        print("No viable products match filters."); return

    os.makedirs(args.maps_dir, exist_ok=True)
    styles = getSampleStyleSheet()
    S = {
      "title": ParagraphStyle("t", parent=styles["Title"], textColor=DARK, fontSize=22),
      "h": ParagraphStyle("h", parent=styles["Heading2"], textColor=MED, fontSize=14),
      "cap": ParagraphStyle("c", parent=styles["Normal"], alignment=TA_CENTER, fontSize=9,
                            textColor=colors.grey),
      "leg": ParagraphStyle("l", parent=styles["Normal"], fontSize=9),
      "body": ParagraphStyle("b", parent=styles["Normal"], fontSize=10),
    }
    tag = (args.country or "GHA") + ("_" + args.crop if args.crop else "")
    out_pdf = args.out or f"Planting_Report_{tag}_{args.year}.pdf"
    story = [Paragraph(f"Crop Planting-Window Report", S["title"]),
             Paragraph(f"{args.country or 'All viable countries'} &middot; "
                       f"{(args.crop or 'all crops').title()} &middot; {args.year}", S["h"]),
             Paragraph("TomorrowNow / ICPAC — Sentinel-2 red-edge + FPAR + Sentinel-1 SAR "
                       "fusion, LTN-constrained SOS → planting dekad, WRSI cross-check.", S["body"]),
             Spacer(1, 0.5 * cm)]

    MAP_W, MAP_H = 17.4 * cm, 20.0 * cm

    for r in rows:
        c, crop, season = r["country"], r["crop"].lower(), r["season"]
        adm0 = GAUL_NAME[c]
        adm0_fc = ZA.gaul_admin(ee, [adm0], level=0)
        aoi = adm0_fc.geometry()
        region = aoi.bounds()
        sos_start, sos_end = utils.sos_window_dekads(r["sos_detection_window"])
        win_start, win_end = utils.sos_window_dekads(r["indicative_planting_window"])
        print(f"\n=== {c} | {crop} | {season} === (planting window dekads {win_start}-{win_end})")

        s2_ic  = S2.build_s2_dekadal(ee, aoi, args.year)
        s1_ic  = S1.build_s1_dekadal(ee, aoi, args.year, orbit=args.orbit)
        fpar_ic= FZ.add_fpar_dekadal(ee, aoi, args.year)
        g_ic   = FZ.build_fused_greenness(ee, s2_ic, s1_ic, fpar_ic)
        mask   = crop_mask_image(ee, crop, args.mask_asset)
        sos    = FZ.detect_sos(ee, g_ic, mask, sos_start, sos_end, ltn_sos=None)
        planting = PD.sos_to_planting(ee, sos, crop)
        metric = SK.means_metric_image(ee, planting, mask, win_start, win_end,
                                       g_ic=g_ic, sos_img=sos,
                                       sos_start=sos_start, sos_end=sos_end)

        # assemble the list of (title, ee-image, vis, legend-rows) to render
        pmin, pmax = win_start - 3, win_end + 3
        layers = [
          ("Planting dekad",
           planting.updateMask(mask),
           {"min": pmin, "max": pmax, "palette": PAL_DEKAD},
           [(PAL_DEKAD[0], f"earlier (≤ {utils.dekad_label(max(1,pmin))})"),
            (PAL_DEKAD[2], f"calendar window {utils.dekad_label(win_start)}–{utils.dekad_label(win_end)}"),
            (PAL_DEKAD[-1], f"later (≥ {utils.dekad_label(min(36,pmax))})")]),
          ("Skill vs FEWS/FAO calendar window",
           metric.select("hit"),
           {"min": 0, "max": 1, "palette": PAL_HIT},
           [(PAL_HIT[1], "planted inside the calendar window (hit)"),
            (PAL_HIT[0], "outside the calendar window (miss)")]),
          ("Signal strength (green-up amplitude)",
           metric.select("amp"),
           {"min": 0.0, "max": 0.6, "palette": PAL_AMP},
           [(PAL_AMP[-1], "strong, clear green-up (high confidence)"),
            (PAL_AMP[0], "weak signal (low confidence / mixed pixels)")]),
        ]

        if not args.no_wrsi:
            try:
                whc_img = None
                if soil_cfg.get("use_spatial_whc"):
                    rd_cm = int(kc_cfg[crop].get("root_depth_m", 1.0) * 100)
                    whc_img = SOIL.get_whc(ee, aoi, soil_cfg, root_depth_cm=rd_cm)  # Saxton/SoilGrids default
                wrsi = WR.run_wrsi(ee, aoi, args.year, planting, crop, kc_cfg, soil_cfg,
                                   sos_start, sos_end, whc_img=whc_img)
                layers.insert(1, ("WRSI — water requirement satisfaction",
                    wrsi["WRSI"].updateMask(mask),
                    {"min": 0, "max": 100, "palette": PAL_WRSI},
                    [(PAL_WRSI[-1], "WRSI ≥ 80 (good / no deficit)"),
                     (PAL_WRSI[2], "WRSI 50–80 (mediocre)"),
                     (PAL_WRSI[0], "WRSI < 50 (crop failure risk)")]))
            except Exception as e:
                print(f"  WRSI layer skipped: {e}")

        story.append(PageBreak())
        story.append(Paragraph(f"{c} &middot; {crop.title()} &middot; {season}", S["h"]))
        for name, img, vis, leg in layers:
            png = os.path.join(args.maps_dir, f"{c}_{crop}_{season}_{name[:14]}".replace(" ", "") + ".png")
            try:
                styled_img = styled(ee, img, vis, adm0_fc)
                thumb(ee, styled_img, region, png)
                story += [Spacer(1, 0.2 * cm), Paragraph(name, S["h"]),
                          fit(png, MAP_W, MAP_H * 0.72),
                          legend_table(leg, S), PageBreak()]
                print(f"  rendered: {name}")
            except Exception as e:
                story += [Paragraph(name, S["h"]),
                          Paragraph(f"[map could not be rendered: {e}]", S["cap"]), PageBreak()]
                print(f"  FAILED  : {name} -> {e}")

    SimpleDocTemplate(out_pdf, pagesize=A4,
                      leftMargin=1.8*cm, rightMargin=1.8*cm,
                      topMargin=1.6*cm, bottomMargin=1.6*cm).build(story)
    print(f"\nPDF saved: {os.path.abspath(out_pdf)}")


if __name__ == "__main__":
    main()
