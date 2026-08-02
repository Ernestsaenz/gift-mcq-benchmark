"""Confirm the source of the residual +7%: item x condition heterogeneity that is
correlated ACROSS models within an item."""
import json, math, random
HERE = '/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis'
raw = json.load(open(HERE + '/paired_clean.json'))
cells = [r for r in raw if r.get('analysis_include') is True]
MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]
d = {}
for r in cells:
    d[(r['question_id'], r['model'])] = r['A_correct'] - r['B_correct']
items = sorted(set(r['question_id'] for r in cells))
print("cells=%d items=%d" % (len(cells), len(items)))
print("Cross-MODEL correlation of within-cell d = A_correct - B_correct")
print("(if the residual +7% is item x condition heterogeneity, these must be POSITIVE)")
tot = []
for a in range(4):
    for b in range(a + 1, 4):
        xs = [(d[(it, MODELS[a])], d[(it, MODELS[b])]) for it in items
              if (it, MODELS[a]) in d and (it, MODELS[b]) in d]
        n = len(xs); mx = sum(p[0] for p in xs) / n; my = sum(p[1] for p in xs) / n
        sxy = sum((p[0] - mx) * (p[1] - my) for p in xs)
        sxx = sum((p[0] - mx) ** 2 for p in xs); syy = sum((p[1] - my) ** 2 for p in xs)
        r_ = sxy / math.sqrt(sxx * syy); tot.append(r_)
        random.seed(7); cnt = 0; NP = 2000
        ys = [p[1] for p in xs]
        for _ in range(NP):
            random.shuffle(ys)
            s2 = sum((xs[i][0] - mx) * (ys[i] - my) for i in range(n))
            if s2 / math.sqrt(sxx * syy) >= r_: cnt += 1
        print("  %-10s vs %-10s n=%d r=%+.4f  perm p=%.4f"
              % (MODELS[a].split('/')[1][:10], MODELS[b].split('/')[1][:10], n, r_,
                 (cnt + 1) / (NP + 1.0)))
print("  mean pairwise cross-model r = %+.4f" % (sum(tot) / len(tot)))

alld = [d[k] for k in d]
gm = sum(alld) / len(alld)
byit = {}
for (it, m), v in d.items(): byit.setdefault(it, []).append(v)
k_ = len(byit); ni = [len(v) for v in byit.values()]
msb = sum(len(v) * ((sum(v) / len(v)) - gm) ** 2 for v in byit.values()) / (k_ - 1)
msw = sum(sum((x - (sum(v) / len(v))) ** 2 for x in v) for v in byit.values()) / (len(alld) - k_)
n0 = (sum(ni) - sum(x * x for x in ni) / sum(ni)) / (k_ - 1)
print("\n  ANOVA ICC of d across models within item = %.4f (MSB=%.4f MSW=%.4f n0=%.2f)"
      % ((msb - msw) / (msb + (n0 - 1) * msw), msb, msw, n0))
