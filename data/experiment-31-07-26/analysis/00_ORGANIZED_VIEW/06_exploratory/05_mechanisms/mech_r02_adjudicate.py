"""Independent adjudication of stem polarity + audit sweep.

My labels (MINE_NEG) were produced by reading every trailing interrogative clause of the
241 flag=False items and all 84 flag=True items.  This script then does an ADVERSARIAL
sweep: it applies a deliberately over-broad case-INSENSITIVE negation lexicon to the FULL
stem of every item I called non-negated, so any negation cue my tail-extraction truncated
gets surfaced for a second read.
"""
import json, re, sys

BASE = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/"
D = json.load(open(BASE + "mech_r02_stems.json"))
ids = sorted(D, key=lambda q: int(re.sub(r"\D", "", q) or 0))

# ---- my hand adjudication of flag=False items judged NEGATED -------------------------
MINE_MISS = """b77 b83 b87 b116 b136 b148 b153 b159 b163 b167 b173 b182 b184 b186 b201 b208
b215 b221 b223 b227 b232 b234 b244 b247 b248 b260 b262 b268 b274 b283 b287 b294 b309 b317
b318 b319 b322 b323 b332 b338 b339 b345 b349 b354 b359 b360 b362 b363 b374 b386 b392 b411
b414 b422 b433 b440 b441 b443 b451 b457 b459 b464 b472 b475 b481 b499""".split()

BORDERLINE = {"b411", "b442", "b320"}   # judged separately, see notes

MINE_NEG = set(MINE_MISS) | {q for q in ids if D[q]["flag"]}

# ---- adversarial over-broad lexicon over the FULL stem -------------------------------
BROAD = [r"\bno\b", r"\bnunca\b", r"\bexcepto\b", r"\bsalvo\b", r"\bfals[oa]s?\b",
         r"\bincorrect[oa]s?\b", r"\berr[oó]ne[oa]s?\b", r"\bmenos un[ao]\b",
         r"\bexclu", r"\bcontraindicad", r"\bdesaconsej", r"\bmenor(?:es)? probab",
         r"\ben contra\b", r"\bnegativ"]
RX = re.compile("|".join(BROAD), re.IGNORECASE)

def norm(s): return " ".join(s.split())

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "summary"

    if mode == "sweep":
        # every item I called NON-negated that nonetheless trips the broad lexicon
        n = 0
        for q in ids:
            if q in MINE_NEG: continue
            s = norm(D[q]["stem"])
            hits = sorted({m.group(0).lower() for m in RX.finditer(s)})
            if not hits: continue
            n += 1
            print("%-6s flag=%-5s hits=%s" % (q, D[q]["flag"], hits))
            print("      ", s[-260:])
        print("\nnon-negated items tripping broad lexicon:", n)
        return

    if mode == "clean":
        # items I called non-negated AND the broad lexicon agrees -> safe agreements
        n = sum(1 for q in ids if q not in MINE_NEG and not RX.search(norm(D[q]["stem"])))
        print("clean non-negated (no cue anywhere in full stem):", n)
        return

    # ---- summary -------------------------------------------------------------------
    flagT = {q for q in ids if D[q]["flag"]}
    neg = MINE_NEG
    tp = len(flagT & neg); fp = len(flagT - neg); fn = len(neg - flagT)
    N = len(ids)
    print("items                         : %d" % N)
    print("shipped flag=True             : %d (%.1f%%)" % (len(flagT), 100*len(flagT)/N))
    print("adjudicated negated (mine)    : %d (%.1f%%)" % (len(neg), 100*len(neg)/N))
    print("  ... excluding borderline    : %d (%.1f%%)" %
          (len(neg - BORDERLINE), 100*len(neg - BORDERLINE)/N))
    print("precision  tp/(tp+fp)         : %d/%d = %.3f" % (tp, tp+fp, tp/(tp+fp)))
    print("recall     tp/(tp+fn)         : %d/%d = %.3f" % (tp, tp+fn, tp/(tp+fn)))
    print("  ... excluding borderline    : %d/%d = %.3f" %
          (tp, len(neg - BORDERLINE), tp/len(neg - BORDERLINE)))
    print("error rate over all items     : %d/%d = %.3f" % (fn, N, fn/N))
    print("error rate among truly negated: %d/%d = %.3f" % (fn, len(neg), fn/len(neg)))

    # ---- marker bucket for each miss --------------------------------------------------
    def bucket(s):
        s = norm(s)
        if re.search(r"\bEXCEPTO\b", s): return "EXCEPTO (upper)"
        if re.search(r"\bexcepto\b", s): return "excepto (lower, unflagged?)"
        if re.search(r"FALS[OA]S?\b", s): return "FALSO/FALSA (upper)"
        if re.search(r"INCORRECT[OA]S?\b", s): return "INCORRECTO/A (upper)"
        if re.search(r"ERR[OÓ]NE[OA]\b", s): return "ERRONEA (upper)"
        if re.search(r"\bmenos un[ao]\b", s, re.I): return "menos una"
        if re.search(r"\bNO\b", s): return "bare NO (upper, unmatched form)"
        if re.search(r"\bno\b", s): return "bare no (lower)"
        return "other"

    from collections import Counter
    c = Counter(bucket(D[q]["stem"]) for q in sorted(neg - flagT))
    print("\nmisses by marker:")
    for k, v in c.most_common(): print("  %-32s %d" % (k, v))

    # collapse to the claim's 5 buckets
    def bucket5(s):
        b = bucket(s)
        if b.startswith("EXCEPTO"): return "EXCEPTO"
        if b.startswith("FALS"): return "uppercase FALSO/FALSA"
        if b.startswith("INCORRECT"): return "uppercase INCORRECTO/A"
        if b == "menos una": return "menos una"
        return "bare 'no'"
    c5 = Counter(bucket5(D[q]["stem"]) for q in sorted(neg - flagT))
    print("\nmisses collapsed to the claim's 5 buckets:")
    for k, v in c5.most_common(): print("  %-26s %d" % (k, v))

    # ---- has_context split -----------------------------------------------------------
    recs = [r for r in json.load(open(BASE + "paired_clean.json")) if r["analysis_include"]]
    ctx = {}
    for r in recs: ctx[r["question_id"]] = bool(r["has_context"])
    nc = sum(1 for q in (neg - flagT) if not ctx[q])
    print("\nmisses that are no-context items: %d/%d" % (nc, len(neg - flagT)))
    print("all items no-context            : %d/%d" % (sum(1 for q in ids if not ctx[q]), N))
    print("negated & no-context            : %d/%d" % (sum(1 for q in neg if not ctx[q]), len(neg)))
    print("flag=True & no-context          : %d/%d" % (sum(1 for q in flagT if not ctx[q]), len(flagT)))

if __name__ == "__main__":
    main()
