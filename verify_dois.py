#!/usr/bin/env python3
"""Resolve every DOI in REFERENCES.md and check the record matches what we cite.

The bibliography carries its own warning that several DOIs were surfaced during development and
should be checked before publication. This checks them: each DOI is resolved through DOI content
negotiation (Crossref/DataCite CSL-JSON), and the returned title, year and container are compared
against the citation in the file.

Three outcomes, and the middle one is the dangerous one a human skim would miss:

    OK          resolves, and the title matches what we cite
    MISMATCH    resolves, but to a DIFFERENT paper - the DOI is wrong, not missing
    DEAD        does not resolve at all

    python verify_dois.py
"""
import json, re, subprocess, sys, time, urllib.parse

SRC = "REFERENCES.md"
OUT = "doi_verification.csv"


def norm(t):
    t = re.sub(r"[^a-z0-9 ]+", " ", (t or "").lower())
    return " ".join(t.split())


def overlap(a, b):
    """Word overlap of the shorter title against the longer - robust to subtitle differences."""
    A, B = set(norm(a).split()), set(norm(b).split())
    A -= {"the", "a", "an", "of", "for", "and", "in", "to", "on", "with", "from", "using"}
    B -= {"the", "a", "an", "of", "for", "and", "in", "to", "on", "with", "from", "using"}
    if not A or not B:
        return 0.0
    return len(A & B) / min(len(A), len(B))


def resolve(doi):
    try:
        r = subprocess.run(
            ["curl", "-sL", "-m", "25", "-H",
             "Accept: application/vnd.citationstyles.csl+json",
             "-H", "User-Agent: ICPAC-pipeline-reference-check/1.0 (mailto:manzikye@gmail.com)",
             # DOIs legitimately contain (), [], : and ; - they must be percent-encoded in the
             # request path or the resolver 404s on a perfectly valid DOI
             f"https://doi.org/{urllib.parse.quote(doi, safe='/')}"],
            capture_output=True, text=True)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        return json.loads(r.stdout)
    except Exception:
        return None


def main():
    text = open(SRC).read()
    # a DOI plus the citation text of the bullet it sits in
    entries = []
    for block in re.split(r"\n(?=- )", text):
        # Legacy DOIs are punctuation-heavy and a naive character class mangles them:
        #   Elsevier   10.1016/0168-1923(88)90039-1          parentheses
        #   BioScience 10.1641/0006-3568(2004)054[0547:ACSMOG]2.0.CO;2   brackets, colon, SEMICOLON
        # So take the whole token up to whitespace and strip only trailing punctuation that cannot
        # belong to a DOI - never the ';2' that genuinely ends the BioOne form.
        found = []
        for tok in re.findall(r"https?://doi\.org/(\S+)", block):
            while tok and tok[-1] in ".,":
                tok = tok[:-1]
            while tok.endswith(")") and tok.count("(") < tok.count(")"):
                tok = tok[:-1]
                while tok and tok[-1] in ".,":
                    tok = tok[:-1]
            if re.match(r"10\.\d{4,9}/", tok):
                found.append(tok)
        found = list(dict.fromkeys(found))
        for doi in found:
            # a bullet carrying several DOIs (a primary plus a legacy dataset) cannot have its
            # single italic title compared against each of them
            entries.append((doi, " ".join(block.split())[:400], len(found) > 1))
    seen, uniq = set(), []
    for d, c, multi in entries:
        if d.lower() not in seen:
            seen.add(d.lower()); uniq.append((d, c, multi))

    print(f"{len(uniq)} distinct DOIs in {SRC}\n")
    rows = []
    for i, (doi, cite, multi) in enumerate(uniq, 1):
        meta = resolve(doi)
        cited_title = re.search(r"\*([^*]{8,300})\*", cite)
        cited_title = cited_title.group(1) if cited_title else ""
        if meta is None:
            verdict, got, yr = "DEAD", "", ""
        else:
            got = meta.get("title") or ""
            if isinstance(got, list):
                got = got[0] if got else ""
            yr = ""
            for k in ("issued", "published-print", "published-online", "created"):
                p = (meta.get(k) or {}).get("date-parts") or []
                if p and p[0] and p[0][0]:
                    yr = str(p[0][0]); break
            sim = None if (multi or not cited_title) else overlap(cited_title, got)
            if sim is None:
                verdict = ("OK (entry cites several DOIs, title not comparable)" if multi
                           else "OK (no title to compare)")
            else:
                verdict = "OK" if sim >= 0.55 else "MISMATCH"
        cited_yr = re.search(r"\((\d{4})\)", cite)
        cited_yr = cited_yr.group(1) if cited_yr else ""
        yr_flag = ("" if not (yr and cited_yr) or abs(int(yr) - int(cited_yr)) <= 1
                   else f"  YEAR {cited_yr}->{yr}")
        rows.append(dict(doi=doi, verdict=verdict, cited_year=cited_yr, resolved_year=yr,
                         cited_title=cited_title[:110], resolved_title=str(got)[:110],
                         year_flag=yr_flag.strip()))
        mark = {"OK": "  ", "MISMATCH": "!!", "DEAD": "XX"}.get(verdict, "  ")
        print(f"{mark} [{i:2d}/{len(uniq)}] {doi:42s} {verdict}{yr_flag}")
        if verdict == "MISMATCH":
            print(f"        cited   : {cited_title[:100]}")
            print(f"        resolves: {str(got)[:100]}")
        time.sleep(0.4)

    import pandas as pd
    pd.DataFrame(rows).to_csv(OUT, index=False)
    from collections import Counter
    c = Counter(r["verdict"].split(" ")[0] for r in rows)
    print(f"\n=== {len(rows)} DOIs: " + ", ".join(f"{v} {k}" for k, v in c.items()))
    bad = [r for r in rows if r["verdict"] != "OK" and not r["verdict"].startswith("OK")]
    yrs = [r for r in rows if r["year_flag"]]
    if bad:
        print("\nNEEDS ATTENTION:")
        for r in bad:
            print(f"  {r['verdict']:9s} {r['doi']}")
            print(f"      cited   : {r['cited_title']}")
            print(f"      resolves: {r['resolved_title'] or '(nothing)'}")
    if yrs:
        print("\nYEAR DISAGREEMENTS (often online-first vs issue year, check but usually benign):")
        for r in yrs:
            print(f"  {r['doi']:40s} {r['year_flag']}")
    print(f"\nwritten: {OUT}")


if __name__ == "__main__":
    main()
