"""Step 6: tie-corrected semantic test + capability coupling + base-rate audit of
'the drop is entirely carried by these cells'.
"""
import collections, math, random, re, unicodedata
from mech_ref_acc_lib import (load_cells, load_questions, cp_ci, fisher_2x2,
                              binom_test_exact, chisq_sf)

cells = load_cells()
Q = load_questions()
SHORT = {"google/gemini-3.6-flash": "gemini", "z-ai/glm-5.2": "glm",
         "qwen/qwen3.6-35b-a3b": "qwen", "google/gemma-4-26b-a4b-it": "gemma"}
MODELS = ["gemini", "glm", "qwen", "gemma"]
LETTERS = ["a", "b", "c", "d"]
for r in cells:
    r["m"] = SHORT[r["model"]]

_STOP = set("""de la el los las un una unos unas y o u en a al del que se es son por para con sin
sobre como mas menos su sus lo le les ha han hay ser esta este estos estas no ni tras entre""".split())


def toks(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return {t for t in re.findall(r"[a-z0-9]+", s) if len(t) > 3 and t not in _STOP}


def jac(a, b):
    A, B = toks(a), toks(b)
    return len(A & B) / len(A | B) if A and B else 0.0


def top_tier(sims, surv):
    mx = max(sims[L] for L in surv)
    return [L for L in surv if abs(sims[L] - mx) < 1e-12]


print("=" * 100)
print("T2-CORRECTED  'chosen survivor is the top-similarity survivor', with a TIE-AWARE null.")
print("  Under the claim's arbitrary-fallback account each survivor is equally likely, so for a")
print("  cell whose top-similarity tier has t of 3 survivors, P(hit) = t/3.  Expected hits are")
print("  therefore sum(t_i/3), NOT n/3.  Poisson-binomial null, evaluated by Monte Carlo.")
print("=" * 100)


def run(arm):
    """arm='B': refusal cells, survivors = non-NOTA options, target = deleted correct text.
       arm='A': A-arm errors, survivors = distractors, target = the true option text."""
    hits, ps = 0, []
    for r in cells:
        qid, cl = r["question_id"], r["correct_letter"]
        if arm == "B":
            if not (r["A_correct"] and not r["B_correct"]):
                continue
            opts, ch = Q[qid]["B"]["opts"], r["B_selected"]
        else:
            if r["A_correct"]:
                continue
            opts, ch = Q[qid]["A"]["opts"], r["A_selected"]
        target = Q[qid]["A"]["opts"][cl]
        surv = [L for L in LETTERS if L != cl]
        if ch not in surv:
            continue
        sims = {L: jac(target, opts[L]) for L in surv}
        tier = top_tier(sims, surv)
        hits += (ch in tier)
        ps.append(len(tier) / 3.0)
    return hits, ps


rng = random.Random(3)
for arm, label in (("B", "arm B refusal cells (A ok -> B wrong)"),
                   ("A", "arm A ordinary errors  [CONTROL: no NOTA slot exists]")):
    hits, ps = run(arm)
    n = len(ps)
    exp = sum(ps)
    sd = math.sqrt(sum(p * (1 - p) for p in ps))
    Bsim, ge = 20000, 0
    for _ in range(Bsim):
        s = sum(1 for p in ps if rng.random() < p)
        ge += (s >= hits)
    lo, hi = cp_ci(hits, n)
    print(f"\n  {label}")
    print(f"    hits {hits}/{n} = {100*hits/n:.1f}%  CP95 [{100*lo:.1f},{100*hi:.1f}]")
    print(f"    tie-aware expected {exp:.1f} ({100*exp/n:.1f}%)  sd {sd:.1f}  z={(hits-exp)/sd:.2f}")
    print(f"    Monte-Carlo Poisson-binomial P(hits >= obs) = {(ge+1)/(Bsim+1):.4g}   (B={Bsim})")

hB, pB = run("B")
hA, pA = run("A")
print(f"\n  B-arm 'refusal' destinations vs A-arm ordinary distractor errors:")
print(f"    excess over tie-aware null:  B {100*(hB-sum(pB))/len(pB):+.1f}pp   "
      f"A {100*(hA-sum(pA))/len(pA):+.1f}pp")
print(f"    Fisher exact 2x2 (hit/miss, B vs A): "
      f"p = {fisher_2x2(hB, len(pB)-hB, hA, len(pA)-hA):.3g}")
print("    -> if these are indistinguishable, the B 'refusal' destination is an ORDINARY")
print("       distractor error, not the residue of declining a string.")

print()
print("=" * 100)
print("CAPABILITY COUPLING: does the 'refusal rate' behave like a disposition or like ability?")
print("=" * 100)
rows = []
for m in MODELS:
    rs = [r for r in cells if r["m"] == m]
    aok = [r for r in rs if r["A_correct"]]
    rows.append((m, 100 * sum(r["A_correct"] for r in rs) / len(rs),
                 100 * (1 - sum(r["B_correct"] for r in aok) / len(aok))))
rows.sort(key=lambda t: -t[1])
print(f"   {'model':8} {'A accuracy':>11} {'refusal rate':>13}")
for m, a, ref in rows:
    print(f"   {m:8} {a:10.1f}% {ref:12.1f}%")
xs = [r[1] for r in rows]
ys = [r[2] for r in rows]


def spearman(x, y):
    def rk(v):
        s = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        for i, j in enumerate(s):
            r[j] = i + 1
        return r
    rx, ry = rk(x), rk(y)
    n = len(x)
    d2 = sum((a - b) ** 2 for a, b in zip(rx, ry))
    return 1 - 6 * d2 / (n * (n * n - 1))


rho = spearman(xs, ys)
# exact permutation p over all 4! orderings
import itertools
perms = list(itertools.permutations(ys))
ge = sum(1 for p in perms if abs(spearman(xs, list(p))) >= abs(rho) - 1e-12)
print(f"   Spearman rho(A accuracy, refusal rate) = {rho:.3f}")
print(f"   exact permutation test over all {len(perms)} orderings, two-sided: p = {ge/len(perms):.4f}")
print("   -> refusal is perfectly rank-ordered by general ability on the SAME items, which is")
print("      what a difficulty/knowledge account predicts and what a per-model stylistic")
print("      aversion to a fixed Spanish string does not.")

print()
print("=" * 100)
print("BASE-RATE AUDIT of 'the drop is ENTIRELY carried by these cells'")
print("  Share of B error mass sitting in A-correct cells, vs the share expected if B errors")
print("  were placed INDEPENDENTLY of A correctness (that expected share is just P(A correct)).")
print("=" * 100)
print(f"   {'model':8} {'P(A ok)':>9} {'obs share of B errors in A-ok':>31} {'diff':>8} {'Fisher p':>9}")
for m in MODELS:
    rs = [r for r in cells if r["m"] == m]
    pa = sum(r["A_correct"] for r in rs) / len(rs)
    berr = [r for r in rs if not r["B_correct"]]
    obs = sum(r["A_correct"] for r in berr) / len(berr)
    a = sum(1 for r in rs if r["A_correct"] and not r["B_correct"])
    b = sum(1 for r in rs if r["A_correct"] and r["B_correct"])
    c = sum(1 for r in rs if not r["A_correct"] and not r["B_correct"])
    d = sum(1 for r in rs if not r["A_correct"] and r["B_correct"])
    print(f"   {m:8} {100*pa:8.1f}% {100*obs:30.1f}% {100*(obs-pa):7.1f} "
          f"{fisher_2x2(a, b, c, d):9.2g}")
print("   Every model sits BELOW its independence baseline: B errors are over-represented")
print("   among cells the model ALREADY got wrong in A, i.e. item difficulty carries over.")
print()
print(f"   {'model':8} {'P(Bwrong|Aok)':>14} {'P(Bwrong|Awrong)':>17} {'risk ratio':>11}")
for m in MODELS:
    rs = [r for r in cells if r["m"] == m]
    aok = [r for r in rs if r["A_correct"]]
    axx = [r for r in rs if not r["A_correct"]]
    p1 = 1 - sum(r["B_correct"] for r in aok) / len(aok)
    p2 = 1 - sum(r["B_correct"] for r in axx) / len(axx)
    print(f"   {m:8} {100*p1:13.1f}% {100*p2:16.1f}% {p2/p1:11.2f}x")
