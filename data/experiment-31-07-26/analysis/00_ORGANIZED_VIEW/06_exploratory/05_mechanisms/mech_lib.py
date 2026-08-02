"""Shared helpers for mech_* error-destination analysis. Stdlib only."""
import json, sqlite3, re, math, unicodedata

DB = "file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro"
PAIRED = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
LETTERS = ["a", "b", "c", "d"]
IDX = {"a": 2, "b": 3, "c": 4, "d": 5}


def load_questions():
    c = sqlite3.connect(DB, uri=True)
    q = {}
    for ds, key in (("balanced_a_310726", "A"), ("balanced_b_310726", "B")):
        for r in c.execute(
            "select q.question_id,q.correct_letter,q.option_a,q.option_b,q.option_c,"
            "q.option_d,q.correct_option_text,q.question_text from questions q "
            "join datasets d on d.id=q.dataset_id where d.name=?", (ds,)):
            q.setdefault(r[0], {})[key] = {
                "correct_letter": r[1],
                "opts": {L: r[IDX[L]] for L in LETTERS},
                "correct_text": r[6],
                "qtext": r[7],
            }
    c.close()
    return q


def load_cells():
    d = json.load(open(PAIRED))
    return [r for r in d if r["analysis_include"]]


# ---------- text utils ----------
_STOP = set("""de la el los las un una unos unas y o u en a al del que se es son por para con sin
sobre como mas más menos su sus lo le les ha han hay ser esta este estos estas the of""".split())


def strip_acc(s):
    return "".join(ch for ch in unicodedata.normalize("NFD", s)
                   if unicodedata.category(ch) != "Mn")


def toks(s):
    s = strip_acc(s.lower())
    return [t for t in re.findall(r"[a-z0-9]+", s) if len(t) > 2 and t not in _STOP]


def jaccard(a, b):
    A, B = set(toks(a)), set(toks(b))
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


# ---------- stats ----------
def chisq_gof(obs, exp):
    """Pearson chi-square goodness of fit. Returns (X2, df)."""
    x2 = sum((o - e) ** 2 / e for o, e in zip(obs, exp) if e > 0)
    return x2, len(obs) - 1


def chisq_sf(x2, df):
    """Upper tail of chi-square. Exact for even df; erfc-based series for odd df."""
    if x2 <= 0:
        return 1.0
    if df == 1:
        return math.erfc(math.sqrt(x2 / 2.0))
    if df == 2:
        return math.exp(-x2 / 2.0)
    # recurrence: sf(df) = sf(df-2) + x^(df/2-1) e^{-x/2} / (2^{df/2-1} Gamma(df/2))
    k = df
    if k % 2 == 0:
        s, term = math.exp(-x2 / 2.0), math.exp(-x2 / 2.0)
        for i in range(1, k // 2):
            term *= (x2 / 2.0) / i
            s += term
        return s
    s = math.erfc(math.sqrt(x2 / 2.0))
    term = math.sqrt(2.0 * x2 / math.pi) * math.exp(-x2 / 2.0)
    s += term
    i = 3
    while i < k:
        term *= x2 / i
        s += term
        i += 2
    return min(1.0, s)


def binom_two_sided(k, n, p=0.5):
    """Exact two-sided binomial test (method-of-small-p)."""
    if n == 0:
        return 1.0
    def pmf(i):
        return math.comb(n, i) * p ** i * (1 - p) ** (n - i)
    obs = pmf(k)
    tot = sum(pmf(i) for i in range(n + 1) if pmf(i) <= obs * (1 + 1e-9))
    return min(1.0, tot)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))
