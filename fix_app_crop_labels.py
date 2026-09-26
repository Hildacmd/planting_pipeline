#!/usr/bin/env python3
"""Make every app label name the product's OWN crop instead of saying "maize".

Both apps grew up as maize-only tools and the word was hardcoded in ~20 places: the page title, the
h1, the footer, the ASAP layer notes, the "no maize signal" legend row, the "% of mapped maize area"
summary, and the per-unit detail row that read **'Maize pixels'** for every product. With 18 sorghum,
4 wheat, 2 millet and 1 teff product in the apps, a reader looking at Sudan millet was told it was
looking at maize pixels.

Fix: the UI keeps a `{crop}` token, and `SUB()` substitutes the current product's crop at render
time. Titles use the crop capitalised. Nothing is renamed per product at build time, so switching
product in the selector relabels everything immediately.

The embedded <script id="pw-data"> payload is split off first and reattached untouched - it is ~7 MB
of product JSON that legitimately contains the word "maize" as data, and a blind replace would
corrupt it.

    python fix_app_crop_labels.py            # report what would change
    python fix_app_crop_labels.py --apply
"""
import argparse, re, sys

HELPERS = """
// ---- crop-aware labelling -------------------------------------------------------------------
// These apps serve maize, sorghum, wheat, teff and millet. Every user-visible label carries a
// {crop} token that SUB() fills from the product on screen, so a sorghum product never claims to
// be showing maize. CW() = lower-case crop word, CWC() = capitalised for titles.
function CW(){ return (typeof prod!=='undefined' && prod && prod.crop) ? prod.crop : 'crop'; }
function CWC(){ const c=CW(); return c.charAt(0).toUpperCase()+c.slice(1); }
function SUB(s){ return String(s).replace(/\\{crop\\}/g, CW()).replace(/\\{Crop\\}/g, CWC()); }
"""

# literal -> replacement, applied to the UI only
COMMON = [
    ("['Maize pixels',a.n!=null?a.n.toLocaleString():'—']",
     "[SUB('{Crop} pixels'),a.n!=null?a.n.toLocaleString():'—']"),
    ("['Maize pixels', a.n!=null?a.n.toLocaleString():'—']",
     "[SUB('{Crop} pixels'), a.n!=null?a.n.toLocaleString():'—']"),
]
RISK = [
    ("<title>2024 Maize Risk Monitor — GHA / ICPAC</title>",
     "<title>2024 Crop Risk Monitor — GHA / ICPAC</title>"),
    ('<h1 id="h1title">2024 Maize Risk Monitor</h1>',
     '<h1 id="h1title">2024 Crop Risk Monitor</h1>'),
    ("prod.country+' — 2024 Maize Risk Monitor'",
     "prod.country+' — 2024 '+CWC()+' Risk Monitor'"),
    ("' · ASAP water-balance risk (crop-failure % of maize area)'",
     "' · ASAP water-balance risk (crop-failure % of '+CW()+' area)'"),
    ("Critical ≥75% of maize area in failure",
     "Critical ≥75% of the mapped crop area in failure"),
    ("`<b>${pct.toFixed(1)}%</b> of mapped maize area in ${LAYERS[ca].unit}`",
     "`<b>${pct.toFixed(1)}%</b> of mapped ${CW()} area in ${SUB(LAYERS[ca].unit)}`"),
    ("` · ${nd} units without maize signal`",
     "` · ${nd} units without ${CW()} signal`"),
    ("no maize signal", "no ${CW()} signal"),
    ("${ASAP[c].k} · ${LAYERS[ca].unit}", "${ASAP[c].k} · ${SUB(LAYERS[ca].unit)}"),
]
PW = [
    ("<title>Maize Planting-Window Explorer — GHA / ICPAC</title>",
     "<title>Crop Planting-Window Explorer — GHA / ICPAC</title>"),
    ('<h1 id="h1title">Maize Planting-Window Explorer</h1>',
     '<h1 id="h1title">Crop Planting-Window Explorer</h1>'),
    ("prod.country+' Maize Planting-Window Explorer'",
     "prod.country+' '+CWC()+' Planting-Window Explorer'"),
    ("document.getElementById('sumAttr').textContent=A.label+' — '+A.note",
     "document.getElementById('sumAttr').textContent=SUB(A.label+' — '+A.note)"),
]


def patch(path, extra, apply):
    """Patch the UI only. head and tail are patched SEPARATELY and the ~7 MB product-JSON payload is
    concatenated back between them untouched, so no index arithmetic can slice into the data."""
    s = open(path).read()
    i = s.find('<script id="pw-data"'); j = s.find("</script>", i)
    if i < 0 or j < 0:
        return print(f"  {path}: no pw-data block")
    head, data, tail = s[:i], s[i:j], s[j:]
    if "function SUB(" in head + tail:
        return print(f"  {path}: already patched")

    n = k = 0
    parts = []
    for part in (head, tail):
        for a, b in COMMON + extra:
            if a in part:
                part = part.replace(a, b); n += 1
        part, kk = re.subn(r"(note|unit|el):'[^']*maize[^']*'",
                           lambda m: m.group(0).replace("maize", "{crop}"), part)
        k += kk
        parts.append(part)
    head, tail = parts

    # the app's own <script> sits AFTER the pw-data block, i.e. in the tail
    for idx, part in enumerate((head, tail)):
        m = re.search(r"<script>", part)
        if m:
            part = part[:m.end()] + HELPERS + part[m.end():]
            if idx == 0:
                head = part
            else:
                tail = part
            break
    else:
        return print(f"  {path}: no <script> anchor in either part")

    live = [x.strip()[:110] for x in re.findall(r"[^\n]{0,60}[Mm]aize[^\n]{0,60}", head + tail)
            if not x.strip().startswith("//")]
    print(f"  {path}: {n} label sites fixed, {k} note/unit strings tokenised, "
          f"{len(live)} live 'maize' mentions left")
    for x in live:
        print(f"      still: {x}")
    if apply:
        open(path, "w").write(head + data + tail)
        print(f"    wrote {path}  ({len(head + data + tail)/1048576:.2f} MB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    patch("risk_app.html", RISK, a.apply)
    patch("pw_app.html", PW, a.apply)
    if not a.apply:
        print("\ndry run — re-run with --apply")
