"""Is the reverse-engineered rule uniquely identified?  And spurious-hit diagnostics."""
import json, re, itertools
from collections import Counter

BASE = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/"
D = json.load(open(BASE + "mech_r02_stems.json"))
ids = sorted(D, key=lambda q: int(re.sub(r"\D", "", q) or 0))
import mech_r02_adjudicate as ADJ
NEG = ADJ.MINE_NEG

CLAIM = ['falsa','falso','incorrecta','errónea','excepto','no es cierta','no es correcta',
         'NO es','NO se','NO está','NO esta']
MIN9  = ['falsa','falso','incorrecta','errónea','excepto','no es cierta','no es correcta',
         'NO es','NO se']

def fit(pats, transform=lambda s: s):
    return sum(1 for q in ids
               if any(p in transform(D[q]["stem"]) for p in pats) != D[q]["flag"])

print("claimed 11-pattern rule, case-sensitive : mismatches =", fit(CLAIM))
print("minimal 9-pattern equivalent            : mismatches =", fit(MIN9))
print("  -> the last two patterns are subsumed by 'NO es'; the rule is identified only")
print("     UP TO EQUIVALENCE ON THIS CORPUS, not uniquely.")

# word-boundary regex variant of the same lexicon
RXS = [re.compile(r"\b" + re.escape(p) + r"\b") for p in MIN9]
mm = sum(1 for q in ids if any(r.search(D[q]["stem"]) for r in RXS) != D[q]["flag"])
print("word-boundary regex variant of MIN9     : mismatches =", mm)

# rival: could the rule be case-insensitive over a restricted span?  b173 kills it.
print("\nb173 full stem:", repr(" ".join(D['b173']['stem'].split())), "flag =", D['b173']['flag'])
print("  -> stem is a bare uppercase 'FALSA' prompt with flag=False, so NO case-insensitive")
print("     rule containing 'falsa' can fit.  Case-sensitivity is genuinely forced.")

# spurious-hit diagnostic for a WHOLE-TEXT case-insensitive lexicon
ci = [p.lower() for p in CLAIM]
hit = [q for q in ids if any(p in D[q]["stem"].lower() for p in ci)]
spur = [q for q in hit if q not in NEG]
print("\nwhole-text case-INSENSITIVE claim lexicon: hits=%d, of which non-negated (spurious)=%d"
      % (len(hit), len(spur)))
BROAD_CI = ci + ['no ', 'nunca', 'salvo', 'menos una', 'menos uno']
hit2 = [q for q in ids if any(p in D[q]["stem"].lower() for p in BROAD_CI)]
print("whole-text case-INSENSITIVE + bare 'no ': hits=%d, spurious=%d"
      % (len(hit2), sum(1 for q in hit2 if q not in NEG)))

# consequence: composition of the flag=False stratum
flagF = [q for q in ids if not D[q]["flag"]]
print("\nCONSEQUENCE -- composition of the shipped strata:")
print("  flag=True  n=%3d, truly negated %3d (%.1f%%)"
      % (325-len(flagF), sum(1 for q in ids if D[q]["flag"] and q in NEG),
         100*sum(1 for q in ids if D[q]["flag"] and q in NEG)/(325-len(flagF))))
print("  flag=False n=%3d, truly negated %3d (%.1f%%)  <-- contaminated comparison stratum"
      % (len(flagF), sum(1 for q in flagF if q in NEG),
         100*sum(1 for q in flagF if q in NEG)/len(flagF)))

# adjudication sensitivity band
LOOSE = NEG | {"b442"}
STRICT = NEG - {"b411"}
for nm, S in (("strict (drop b411)", STRICT), ("mine", NEG), ("loose (+b442)", LOOSE)):
    tp = sum(1 for q in S if D[q]["flag"])
    print("adjudication %-20s n_neg=%3d  recall=%.3f  miss=%3d  miss/neg=%.3f"
          % (nm, len(S), tp/len(S), len(S)-tp, (len(S)-tp)/len(S)))
