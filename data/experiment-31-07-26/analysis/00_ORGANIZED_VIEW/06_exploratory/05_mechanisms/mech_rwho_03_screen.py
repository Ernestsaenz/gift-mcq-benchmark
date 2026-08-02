"""R3. Broad screen of item features NOT offered in the claimed model.

If the mechanism is a recognition shortcut, the item feature that should matter most
is a *surface-matching cue*: how much distinctive vocabulary the correct option shares
with the stem relative to the distractors.  That cue is destroyed in condition B.
The claimed model never offered it.  Also screened: option-set homogeneity, digits,
negation inside the correct option, exam year, exam part, region.

Each feature is tested one at a time in
    P(lost | A correct) ~ 3 model dummies + feature
cluster-robust CR1 SEs on the 205 stem-clusters, Wald z, two-sided normal p.
Multiplicity: Holm and Benjamini-Hochberg over the whole screen.
"""
import math, re, unicodedata, collections
from mech_rwho_00_data import cells, items, MODELS
from mech_rwho_lib import run, wald, norm_cdf

STOP = set("""de la el los las un una unos unas y o u en con por para del al a que se su sus
es son ser esta este esto estos estas mas mas menos como sobre entre sin no ni lo le les
cual cuales siguiente siguientes respuesta respuestas opcion opciones correcta correctas
paciente pacientes ante caso senale indique cierta cierto falsa falso""".split())


def nrm(s):
    s = unicodedata.normalize("NFKD", s or "").lower()
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s


def toks(s):
    return set(w for w in re.findall(r"[a-z0-9]{4,}", nrm(s)) if w not in STOP)


def jac(a, b):
    return len(a & b) / len(a | b) if (a | b) else 0.0


# ---- build item-level features ----
for qid, it in items.items():
    L = it["correct_letter"]
    o = it["options"]
    st = toks(it["stem"])
    tc = toks(o[L])
    td = [toks(o[k]) for k in "abcd" if k != L]
    it["ov_correct"] = len(tc & st) / max(len(tc), 1)
    it["ov_dis"] = sum(len(t & st) / max(len(t), 1) for t in td) / 3.0
    it["ov_adv"] = it["ov_correct"] - it["ov_dis"]           # surface-matching cue
    it["ov_raw"] = len(tc & st)                              # raw shared distinctive words
    it["dis_homog"] = sum(jac(td[i], td[j]) for i in range(3) for j in range(i + 1, 3)) / 3.0
    it["cd_sim"] = sum(jac(tc, t) for t in td) / 3.0
    it["correct_odd"] = it["dis_homog"] - it["cd_sim"]       # correct option is the odd one out
    it["n_digit_opts"] = sum(1 for k in "abcd" if re.search(r"\d", o[k]))
    it["correct_has_digit"] = int(bool(re.search(r"\d", o[L])))
    it["correct_negated"] = int(bool(re.search(r"\b(no|nunca|jamas|excepto|salvo|ausencia)\b",
                                               nrm(o[L]))))
    lens = [len(o[k]) for k in "abcd"]
    m = sum(lens) / 4.0
    it["len_cv"] = math.sqrt(sum((x - m) ** 2 for x in lens) / 4.0) / m
    it["mean_opt_chars"] = m
    it["is_caso"] = int(it["exam_part"].startswith("caso") or "casos" in it["exam_part"])

for r in cells:
    r.update({k: v for k, v in items[r["question_id"]].items()
              if k not in ("correct_letter",)})

Ac = [r for r in cells if r["A_correct"] == 1]
MOD = [("model=gemma-4-26b", lambda r: float(r["model"] == MODELS[1])),
       ("model=qwen3.6-35b", lambda r: float(r["model"] == MODELS[2])),
       ("model=glm-5.2", lambda r: float(r["model"] == MODELS[3]))]


def zf(f):
    v = [f(r) for r in Ac]
    m = sum(v) / len(v)
    s = math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))
    return lambda r: (f(r) - m) / s


SCREEN = [
    # -- the recognition-shortcut cue, never offered --
    ("stem-overlap advantage, correct vs distractors (z)", zf(lambda r: r["ov_adv"]), 1),
    ("stem overlap of correct option (z)", zf(lambda r: r["ov_correct"]), 1),
    ("shared distinctive words, stem & correct (z)", zf(lambda r: float(r["ov_raw"])), 1),
    ("stem overlap of distractors (z)", zf(lambda r: r["ov_dis"]), 1),
    # -- can the 3 survivors be rejected as a set? --
    ("distractor-set homogeneity (z)", zf(lambda r: r["dis_homog"]), 1),
    ("correct option is the odd one out (z)", zf(lambda r: r["correct_odd"]), 1),
    ("correct~distractor similarity (z)", zf(lambda r: r["cd_sim"]), 1),
    # -- surface form --
    ("option-length CV (z)", zf(lambda r: r["len_cv"]), 1),
    ("mean option length (z)", zf(lambda r: r["mean_opt_chars"]), 1),
    ("mean distractor length (z)", zf(lambda r: r["mean_dis_chars"]), 1),
    ("# options containing a digit (z)", zf(lambda r: float(r["n_digit_opts"])), 1),
    ("correct option contains a digit", lambda r: float(r["correct_has_digit"]), 1),
    ("correct option is itself negated", lambda r: float(r["correct_negated"]), 1),
    ("stem words (z)", zf(lambda r: float(r["stem_words"])), 1),
    # -- provenance --
    ("exam year (centred 2022)", lambda r: float(r["year"] - 2022), 1),
    ("exam year <= 2019", lambda r: float(r["year"] <= 2019), 1),
    ("clinical-case exam part", lambda r: float(r["is_caso"]), 1),
    ("region = Illes Balears", lambda r: float(r["region"] == "Illes Balears"), 1),
]

print("=" * 100)
print("R3. ONE-AT-A-TIME SCREEN OF ITEM FEATURES THE CLAIMED MODEL NEVER OFFERED")
print(f"    P(lost | A correct) ~ model dummies + feature;  n={len(Ac)}, "
      f"events={sum(r['lost'] for r in Ac)}, clusters={len(set(r['cluster'] for r in Ac))}")
print(f"    {'feature':<52}{'OR':>7}{'95% CI':>20}{'z':>7}{'p':>9}")
res = []
for lab, f, _ in SCREEN:
    b, V, n, _, _ = run(Ac, lambda r: r["lost"], MOD + [(lab, f)], quiet=True)
    j = n.index(lab)
    se = math.sqrt(V[j][j])
    z = b[j] / se
    p = 2 * (1 - norm_cdf(abs(z)))
    res.append((lab, b[j], se, z, p))
    print(f"    {lab:<52}{math.exp(b[j]):>7.3f}"
          f"{'[%.2f, %.2f]' % (math.exp(b[j]-1.96*se), math.exp(b[j]+1.96*se)):>20}"
          f"{z:>7.2f}{p:>9.4f}")

m = len(res)
order = sorted(range(m), key=lambda i: res[i][4])
print("\n    multiplicity over the whole screen (m=%d):" % m)
holm, prev = {}, 0.0
for rank, i in enumerate(order):
    v = max(prev, min(1.0, (m - rank) * res[i][4]))
    holm[i] = v
    prev = v
bh, prev = {}, 1.0
for rank in reversed(range(m)):
    i = order[rank]
    v = min(prev, min(1.0, m * res[i][4] / (rank + 1)))
    bh[i] = v
    prev = v
for i in order[:6]:
    print(f"      {res[i][0]:<52} raw p={res[i][4]:.4f}  Holm={holm[i]:.3f}  BH q={bh[i]:.3f}")
print("      (Holm step-down and Benjamini-Hochberg FDR over the 18 screened features)")
