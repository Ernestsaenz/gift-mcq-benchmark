"""(i, corrected) Deliberation vs echo.

The answer format is a JSON object that ECHOES the chosen option's text, so raw
completion_tokens = thinking tokens + the length of whatever string the model
copied out.  In condition B the correct slot's text is always the fixed 48-char
string "Ninguna de las respuestas anteriores es correcta.", which is SHORTER
than a typical Spanish exam distractor -- so raw completion_tokens is
mechanically biased DOWNWARD in B for any model that does not think.

Decomposition used here:
    deliberation  = usage.completion_tokens_details.reasoning_tokens
    echo          = characters of the emitted JSON answer (content_chars)
Both taken from the stored response bodies.

Statistic: median of the paired ratio B/A, cluster bootstrap (208 clusters,
B=4000, percentile 95% CI), plus an exact two-sided sign test on the direction
of the paired difference.
"""
import math
from collections import Counter
from mech_merge import load_merged
from mech_lib_effort import (MODELS, SHORT, median, mean, quantile,
                             cluster_bootstrap, boot_p_two_sided)

rows = load_merged()
NOTA = "Ninguna de las respuestas anteriores es correcta."


def sign_test(vals):
    pos = sum(1 for v in vals if v > 0)
    neg = sum(1 for v in vals if v < 0)
    n = pos + neg
    if n == 0:
        return pos, neg, 1.0
    lo = min(pos, neg)
    tail = sum(math.exp(math.lgamma(n + 1) - math.lgamma(k + 1)
                        - math.lgamma(n - k + 1) - n * math.log(2.0))
               for k in range(lo + 1))
    return pos, neg, min(1.0, 2 * tail)


print("=" * 104)
print("(i-corrected) EFFORT = REASONING TOKENS ONLY  (echo of the option text removed)")
print(f'   NOTA string = "{NOTA}"  ({len(NOTA)} chars)')
print("=" * 104)
print(f"{'model':<18} {'medReasonA':>11} {'medReasonB':>11} {'medDiff':>8} "
      f"{'medRatio':>9} {'95% CI (cluster boot)':>24} {'p_boot':>9} "
      f"{'B>A':>5} {'B<A':>5} {'p_sign':>11}")


def med_ratio_field(f):
    def g(rs):
        v = [(r["B_" + f] + 1) / (r["A_" + f] + 1) for r in rs]  # +1 guards zeros
        return median(v)
    return g


for m in MODELS:
    rs = [r for r in rows if r["model"] == m]
    ra = [r["A_reason"] for r in rs]
    rb = [r["B_reason"] for r in rs]
    if max(ra + rb) == 0:
        print(f"{SHORT[m]:<18} {0:>11} {0:>11}   -- emits ZERO reasoning tokens in "
              f"both conditions ({len(rs)}/{len(rs)} cells): no deliberation to measure")
        continue
    pt, lo, hi, reps = cluster_bootstrap(rs, med_ratio_field("reason"), B=4000, seed=31)
    pos, neg, ps = sign_test([r["B_reason"] - r["A_reason"] for r in rs])
    print(f"{SHORT[m]:<18} {median(ra):>11.0f} {median(rb):>11.0f} "
          f"{median([b-a for a,b in zip(ra,rb)]):>8.0f} {pt:>9.3f} "
          f"[{lo:>7.3f},{hi:>7.3f}]{'':>6} {boot_p_two_sided(reps,1.0):>9.4g} "
          f"{pos:>5} {neg:>5} {ps:>11.3g}")

print()
print("-" * 104)
print("The ECHO term, in the opposite direction: characters of the emitted JSON answer")
print("-" * 104)
print(f"{'model':<18} {'med chars A':>12} {'med chars B':>12} {'ratio':>7} "
      f"{'med echoed-option chars A':>26} {'B':>6}")
for m in MODELS:
    rs = [r for r in rows if r["model"] == m]
    ca = median([r["A_cchars"] for r in rs])
    cb = median([r["B_cchars"] for r in rs])
    sa = median([r["A_seltext_chars"] for r in rs])
    sb = median([r["B_seltext_chars"] for r in rs])
    print(f"{SHORT[m]:<18} {ca:>12.0f} {cb:>12.0f} {cb/ca:>7.3f} "
          f"{sa:>26.0f} {sb:>6.0f}")

print()
print("-" * 104)
print("How much of the RAW completion-token change is echo vs deliberation?")
print("  raw  = completion_tokens        (what paired_clean.json calls *_tokens)")
print("  think= reasoning_tokens")
print("  rest = raw - think  (answer JSON; unreliable for qwen -- see note)")
print("-" * 104)
print(f"{'model':<18} {'med raw A':>10} {'med raw B':>10} {'d raw':>8} "
      f"{'d think':>9} {'d rest':>9} {'think share of d raw':>21}")
for m in MODELS:
    rs = [r for r in rows if r["model"] == m]
    d_raw = median([r["B_tokens"] - r["A_tokens"] for r in rs])
    d_th = median([r["B_reason"] - r["A_reason"] for r in rs])
    d_rest = median([(r["B_tokens"] - r["B_reason"]) - (r["A_tokens"] - r["A_reason"])
                     for r in rs])
    share = (d_th / d_raw) if d_raw else float("nan")
    print(f"{SHORT[m]:<18} {median([r['A_tokens'] for r in rs]):>10.0f} "
          f"{median([r['B_tokens'] for r in rs]):>10.0f} {d_raw:>8.0f} "
          f"{d_th:>9.0f} {d_rest:>9.0f} "
          f"{('n/a' if d_raw==0 else f'{share*100:.0f}%'):>21}")

print()
print("NOTE on qwen accounting: for 149/650 qwen cells the provider reports")
print("reasoning_tokens > completion_tokens, so 'rest' goes negative there.")
print("reasoning_tokens itself is internally consistent (spearman & pearson with")
print("the raw reasoning-trace character count = 1.000, 3.93 chars/token), so the")
print("deliberation series is trustworthy; only the residual 'rest' is not.")
print("Gemini returns a THOUGHT SUMMARY, not the raw trace (1.47 chars per billed")
print("reasoning token), so for gemini only reasoning_tokens is usable.")

print()
print("=" * 104)
print("Zero-reasoning check: how often does each model think at all?")
print("=" * 104)
print(f"{'model':<18} {'cond':<5} {'% cells with 0 reasoning tokens':>32} "
      f"{'p10':>7} {'p50':>7} {'p90':>8}")
for m in MODELS:
    for c in "AB":
        v = [r[c + "_reason"] for r in rows if r["model"] == m]
        z = 100.0 * sum(1 for x in v if x == 0) / len(v)
        print(f"{SHORT[m]:<18} {c:<5} {z:>32.1f} {quantile(v,.10):>7.0f} "
              f"{quantile(v,.50):>7.0f} {quantile(v,.90):>8.0f}")
