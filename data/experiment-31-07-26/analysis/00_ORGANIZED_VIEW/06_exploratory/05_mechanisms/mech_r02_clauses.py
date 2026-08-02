"""Extract the trailing interrogative clause of each stem and dump for hand adjudication."""
import json, re, sys

D = json.load(open("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/mech_r02_stems.json"))
ids = sorted(D, key=lambda q: (q[0], int(re.sub(r"\D", "", q) or 0)))

def tail(s):
    s = " ".join(s.split())
    # prefer the last '¿...?' question span
    qs = list(re.finditer(r"¿[^¿?]*\?", s))
    if qs:
        cand = qs[-1].group(0)
        if len(cand) >= 15:
            return cand
    # else last sentence-ish chunk
    parts = re.split(r"(?<=[.;:!?])\s+", s)
    parts = [p for p in parts if p.strip()]
    out = parts[-1] if parts else s
    if len(out) < 25 and len(parts) >= 2:
        out = parts[-2] + " " + out
    return out

mode = sys.argv[1] if len(sys.argv) > 1 else "all"
for q in ids:
    t = tail(D[q]["stem"])
    f = D[q]["flag"]
    if mode == "true" and not f: continue
    if mode == "false" and f: continue
    print("%-6s %s | %s" % (q, "T" if f else ".", t))
