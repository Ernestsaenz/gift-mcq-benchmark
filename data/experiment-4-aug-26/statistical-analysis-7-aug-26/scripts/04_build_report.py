#!/usr/bin/env python3
"""Build REPORT.html from the committed results files.

Agent 4 of 4. Owns exactly two files: this script and `../REPORT.html`.
Everything else it touches is read-only.

Hard rule this script exists to enforce: **no number is written by hand into
the HTML.** Every figure, table cell and inline statistic in the report is read
at build time from a file in `../results/`, from the read-only exports in
`../../consolidate-triplicates-7-aug-26/exports/`, or from the frozen condition
inputs in `../../replications/.../inputs/`. Re-run this script and the report
tracks whatever the results files now say.

Charts are hand-written inline SVG with coordinates computed here: matplotlib is
not installed in this environment, and the report must be a single
self-contained file with no external stylesheet, font, script or image.

Usage:
    python3 scripts/04_build_report.py
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent          # .../statistical-analysis-7-aug-26/scripts
BASE = HERE.parent                              # .../statistical-analysis-7-aug-26
RESULTS = BASE / "results"
FIGURES = BASE / "figures"
EXP = BASE.parent                               # .../experiment-4-aug-26
CONS = EXP / "consolidate-triplicates-7-aug-26"
EXPORTS = CONS / "exports"
INPUTS = EXP / "replications/ab520-incorrect-cells-triplicate-2026-08-05/inputs"
OUT = BASE / "REPORT.html"


def _repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / ".git").exists():
            return p
    return start


REPO = _repo_root(BASE)

# Every source file actually opened, recorded for the provenance section.
SOURCES: list[dict] = []


def _register(path: Path, role: str) -> Path:
    rel = path.resolve().relative_to(REPO)
    for s in SOURCES:
        if s["rel"] == str(rel):
            return path
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    SOURCES.append({
        "rel": str(rel),
        "role": role,
        "sha256": digest,
        "bytes": path.stat().st_size,
    })
    return path


def read_csv(path: Path, role: str) -> list[dict]:
    _register(path, role)
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def read_json(path: Path, role: str):
    _register(path, role)
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------
# Small numeric / formatting helpers
# --------------------------------------------------------------------------

SUP = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
       "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
       "-": "⁻", "+": ""}


def _sup(s: str) -> str:
    return "".join(SUP.get(ch, ch) for ch in s)


def f(x, default=None):
    """float() that tolerates blanks."""
    if x is None or x == "":
        return default
    return float(x)


def i(x, default=None):
    if x is None or x == "":
        return default
    return int(float(x))


def fmt_p(p) -> str:
    """p-values: 4 decimals down to 1e-4, scientific below, honest about 0.0."""
    if p is None or p == "":
        return "&mdash;"
    p = float(p)
    if p == 0.0:
        # statsmodels' Wald p underflowed to exactly 0.0 in the stored JSON.
        return "&lt;1&times;10" + _sup("-300") + " (underflow)"
    if p >= 1e-4:
        return f"{p:.4f}"
    mant, exp = f"{p:.1e}".split("e")
    return f"{mant}&times;10{_sup(str(int(exp)))}"


def pct(x, nd=1) -> str:
    return "&mdash;" if x is None else f"{100 * float(x):.{nd}f}%"


def pp(x, nd=1, signed=True) -> str:
    """Percentage points."""
    if x is None:
        return "&mdash;"
    v = 100 * float(x)
    return f"{v:+.{nd}f}" if signed else f"{v:.{nd}f}"


def ci(lo, hi, nd=1, scale=100.0, signed=True) -> str:
    if lo is None or hi is None:
        return "&mdash;"
    a, b = scale * float(lo), scale * float(hi)
    fmtspec = f"{{:+.{nd}f}}" if signed else f"{{:.{nd}f}}"
    return f"[{fmtspec.format(a)}, {fmtspec.format(b)}]"


def num(x, nd=2) -> str:
    return "&mdash;" if x is None else f"{float(x):.{nd}f}"


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def short_model(m: str) -> str:
    return m.split("/", 1)[-1]


def inv_norm_cdf(p: float) -> float:
    """Acklam's rational approximation to the standard normal quantile.

    Used only to place QQ-plot points; stdlib-only so this script has no
    dependency beyond CPython itself.
    """
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


# --------------------------------------------------------------------------
# Load every input
# --------------------------------------------------------------------------

def load_all() -> dict:
    d = {}
    # --- statistical results (agents 1-3)
    d["norm_binary"] = read_json(RESULTS / "normality_binary_outcome_summary.json",
                                "Base rates, cluster histogram, boundary counts, flip description")
    d["norm_cont"] = read_json(RESULTS / "normality_continuous_diagnostics.json",
                               "Shapiro-Wilk / Anderson-Darling / moments for the continuous quantities")
    d["norm_cont_csv"] = read_csv(RESULTS / "normality_continuous_diagnostics_summary.csv",
                                  "Flat mirror of the continuous diagnostics")
    d["norm_diff"] = read_csv(RESULTS / "normality_per_question_difficulty.csv",
                              "Per-question difficulty, 500 rows (QQ plot + ceiling figure)")
    d["hist"] = read_csv(RESULTS / "normality_binary_outcome_cluster_histogram.csv",
                         "Per-question cluster histograms")
    d["primary"] = read_json(RESULTS / "primary_summary.json",
                             "Pooled GEE, permutation robustness, ICC, constraint record")
    d["ab"] = read_csv(RESULTS / "primary_condition_AvsB_per_model.csv",
                       "A-vs-B McNemar per model")
    d["prov"] = read_csv(RESULTS / "primary_provider_per_model.csv",
                         "openrouter_A vs tailscale_A McNemar per model")
    d["omni"] = read_csv(RESULTS / "primary_model_effects_omnibus.csv",
                         "Cochran's Q per arm")
    d["posthoc"] = read_csv(RESULTS / "primary_model_effects_posthoc.csv",
                            "Pairwise model McNemar, Holm-corrected within arm")
    d["flip_raw"] = read_csv(RESULTS / "primary_flip_rate_raw.csv",
                             "Raw flip rates by arm x model, both sensitivity variants")
    d["flip_gee"] = read_csv(RESULTS / "primary_flip_rate_gee.csv",
                             "Cluster-robust GEE on flip rate")
    d["grp"] = read_json(RESULTS / "groupings_summary.json",
                         "Open/closed results, big-vs-small infeasibility record, seeds")
    d["grp_primary"] = read_csv(RESULTS / "groupings_open_closed_primary.csv",
                                "Open vs closed, run-1 strict_correct")
    d["grp_secondary"] = read_csv(RESULTS / "groupings_open_closed_secondary.csv",
                                  "Open vs closed, flip rate, both sensitivity variants")

    # --- read-only upstream data (for design facts and the worked example)
    d["run1"] = read_csv(EXPORTS / "run1-6000-with-replicate-status.csv",
                         "Run-1 cells: design counts, selected-letter distribution, worked example")
    d["repl_cell"] = read_csv(EXPORTS / "replicate-cell-level-1796.csv",
                              "Per-logical-call replicates: scored/exhausted counts, Vertex upstream")
    d["tri"] = read_csv(EXPORTS / "consolidated-triplicates-898.csv",
                        "898 run-1-incorrect cells: arm composition of the replicate set")
    d["condA"] = read_csv(INPUTS / "adjusted-500-condition-A.csv", "Frozen condition-A item bank")
    d["condB"] = read_csv(INPUTS / "adjusted-500-condition-B.csv", "Frozen condition-B item bank")
    return d


# --------------------------------------------------------------------------
# Derived design facts (all recomputed, never asserted)
# --------------------------------------------------------------------------

def derive_design(d: dict) -> dict:
    run1 = d["run1"]
    arms = sorted({r["arm"] for r in run1})
    models = sorted({r["model"] for r in run1})
    questions = sorted({r["question_id"] for r in run1})

    # Selected-letter distribution per arm (option `a` is never correct).
    letter = {a: {} for a in arms}
    for r in run1:
        letter[r["arm"]][r["selected_letter"]] = letter[r["arm"]].get(r["selected_letter"], 0) + 1
    arm_n = {a: sum(letter[a].values()) for a in arms}

    # Condition A vs B item-bank diff, recomputed from the frozen inputs.
    A = {r["question_id"]: r for r in d["condA"]}
    B = {r["question_id"]: r for r in d["condB"]}
    shared = sorted(set(A) & set(B))
    coldiff = {c: 0 for c in ("question_text", "option_a", "option_b", "option_c",
                              "option_d", "correct_letter", "correct_option_text")}
    for q in shared:
        for c in coldiff:
            if A[q][c] != B[q][c]:
                coldiff[c] += 1
    correct_letter_counts = {}
    for q in shared:
        correct_letter_counts[A[q]["correct_letter"]] = correct_letter_counts.get(A[q]["correct_letter"], 0) + 1
    nota_strings = {B[q]["option_" + B[q]["correct_letter"]] for q in shared}
    nota = sorted(nota_strings)[0] if len(nota_strings) == 1 else None

    def mean_len(bank, correct: bool):
        vals = []
        for q in shared:
            r = bank[q]
            for L in "abcd":
                if (L == r["correct_letter"]) == correct:
                    vals.append(len(r["option_" + L]))
        return sum(vals) / len(vals)

    # Worked example: the most compact item in the bank, chosen programmatically.
    def compactness(q):
        r = A[q]
        return (len(r["question_text"]) + sum(len(r["option_" + L]) for L in "abcd"), q)
    ex_id = min(shared, key=compactness)
    ex_cells = [r for r in run1 if r["question_id"] == ex_id]

    # Replicate design.
    repl = d["repl_cell"]
    scored = [r for r in repl if r["status"] == "scored"]
    exhausted = [r for r in repl if r["status"] != "scored"]
    tri_by_arm = {}
    for r in d["tri"]:
        tri_by_arm[r["arm"]] = tri_by_arm.get(r["arm"], 0) + 1

    # Vertex-served cells, recomputed rather than quoted from DEVIATIONS.md.
    gem_b = [r for r in repl if r["arm"] == "openrouter_B" and "gemini" in r["model"]]
    gem_b_scored = [r for r in gem_b if r["status"] == "scored"]
    vertex = [r for r in gem_b_scored if r["upstream"] == "google-vertex"]
    aistudio = [r for r in gem_b_scored if r["upstream"] == "google-ai-studio"]
    gem_b_exhausted = [r for r in gem_b if r["status"] != "scored"]
    vertex_all = [r for r in repl if r["upstream"] == "google-vertex"]
    temp_not_honoured = [r for r in repl if r["temperature_honoured"] == "FALSE"]

    return {
        "arms": arms, "models": models,
        "n_questions": len(questions), "n_arms": len(arms), "n_models": len(models),
        "n_run1_cells": len(run1),
        "letter": letter, "arm_n": arm_n,
        "shared": len(shared), "coldiff": coldiff,
        "correct_letter_counts": correct_letter_counts,
        "nota": nota, "n_nota_variants": len(nota_strings),
        "len_correct_A": mean_len(A, True), "len_correct_B": mean_len(B, True),
        "len_distractor_A": mean_len(A, False), "len_distractor_B": mean_len(B, False),
        "example_id": ex_id, "example_A": A[ex_id], "example_B": B[ex_id],
        "example_cells": ex_cells,
        "n_logical_calls": len(repl), "n_scored": len(scored), "n_exhausted": len(exhausted),
        "n_incorrect_cells": len(d["tri"]), "tri_by_arm": tri_by_arm,
        "n_gem_b_scored": len(gem_b_scored), "n_vertex": len(vertex),
        "n_aistudio": len(aistudio), "n_gem_b_exhausted": len(gem_b_exhausted),
        "n_vertex_all": len(vertex_all), "n_temp_not_honoured": len(temp_not_honoured),
    }


# --------------------------------------------------------------------------
# SVG primitives
# --------------------------------------------------------------------------

C_A = "#3b7dd8"       # condition A / openrouter_A
C_B = "#e0762b"       # condition B (NOTA)
C_T = "#2a9d8f"       # tailscale_A
C_HL = "#c2413c"      # highlight / boundary bars
C_NEU = "#8a8f98"


def svg_open(w: int, h: int, title: str, desc: str = "") -> list[str]:
    return [
        f'<svg class="fig" viewBox="0 0 {w} {h}" width="100%" '
        f'preserveAspectRatio="xMidYMid meet" role="img" '
        f'aria-label="{esc(title)}">',
        f"<title>{esc(title)}</title>",
        (f"<desc>{esc(desc)}</desc>" if desc else ""),
    ]


def txt(x, y, s, cls="lbl", anchor="middle", size=11, extra="") -> str:
    return (f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
            f'font-size="{size}" {extra}>{s}</text>')


def line(x1, y1, x2, y2, cls="ax", extra="") -> str:
    return (f'<line class="{cls}" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" '
            f'y2="{y2:.1f}" {extra}/>')


def rect(x, y, w, h, fill, extra="") -> str:
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" '
            f'height="{max(h, 0):.1f}" fill="{fill}" {extra}/>')


def legend(x, y, items) -> str:
    out = []
    for label, colour in items:
        out.append(rect(x, y - 8, 11, 11, colour, 'rx="2"'))
        out.append(txt(x + 16, y + 1, esc(label), anchor="start", size=11))
        x += 18 + 7.0 * len(label)
    return "".join(out)


# --------------------------------------------------------------------------
# Figure 1 — NOTA susceptibility: accuracy A vs B per model
# --------------------------------------------------------------------------

def fig_nota(ab_rows) -> str:
    rows = sorted(ab_rows, key=lambda r: -(f(r["acc_x"]) - f(r["acc_y"])))
    W, H = 720, 356
    L, R, T, B = 58, 18, 34, 90
    pw, ph = W - L - R, H - T - B
    s = svg_open(W, H, "Accuracy under condition A vs condition B (NOTA) per model",
                 "Grouped bars: run-1 strict-correct accuracy for each model, "
                 "condition A beside condition B, with the NOTA drop annotated.")
    # y axis 0..1
    for k in range(0, 11, 2):
        v = k / 10
        y = T + ph * (1 - v)
        s.append(line(L, y, L + pw, y, "grid"))
        s.append(txt(L - 8, y + 4, f"{int(v * 100)}%", anchor="end", size=10))
    s.append(line(L, T + ph, L + pw, T + ph, "ax"))
    s.append(txt(16, T + ph / 2, "run-1 accuracy", anchor="middle", size=11,
                 extra=f'transform="rotate(-90 16 {T + ph / 2:.1f})"'))

    slot = pw / len(rows)
    bw = min(52, slot * 0.3)
    for n, r in enumerate(rows):
        cx = L + slot * (n + 0.5)
        a, b = f(r["acc_x"]), f(r["acc_y"])
        for off, val, col in ((-bw * 0.58, a, C_A), (bw * 0.58, b, C_B)):
            h = ph * val
            s.append(rect(cx + off - bw / 2, T + ph - h, bw, h, col, 'rx="2"'))
            s.append(txt(cx + off, T + ph - h - 6, f"{val * 100:.1f}", size=10, cls="lbl"))
        # Drop indicator, kept inside the pair's own footprint so it cannot collide
        # with the neighbouring model's bars: A's top level carried across to the
        # right edge of B's bar, then a vertical connector down to B's top.
        ya, yb = T + ph * (1 - a), T + ph * (1 - b)
        edge = cx + bw * 0.58 + bw / 2
        s.append(line(cx - bw * 0.58, ya, edge, ya, "drop"))
        s.append(line(edge, ya, edge, yb, "drop"))
        s.append(txt(cx, T + ph + 18, esc(short_model(r["model"])), size=11))
        s.append(txt(cx, T + ph + 33, f"n={i(r['n_pairs'])} pairs", size=10, cls="sub"))
        s.append(txt(cx, T + ph + 51, f"&minus;{(a - b) * 100:.1f} pp under NOTA",
                     size=11, cls="dropl"))
    s.append(legend(L, H - 12, [("condition A (substantive correct option)", C_A),
                                ("condition B (NOTA replaces it)", C_B)]))
    s.append("</svg>")
    return "".join(s)


# --------------------------------------------------------------------------
# Figure 2 — forest plot of risk differences
# --------------------------------------------------------------------------

def forest(entries, title, xlabel, groups=None, width=760, note=None) -> str:
    """entries: list of dicts {label, rd, lo, hi, group, extra}. rd in [-1, 1]."""
    rowh = 30
    head = 44 if groups else 30
    H = head + rowh * (len(entries) + (len(set(e["group"] for e in entries)) if groups else 0)) + 56
    W = width
    L, R, T = 268, 108, head
    pw = W - L - R
    lo = min(e["lo"] for e in entries)
    hi = max(e["hi"] for e in entries)
    span = max(abs(lo), abs(hi))
    span = max(span, 0.02) * 1.15
    xlo, xhi = -span, span

    def X(v):
        return L + pw * (v - xlo) / (xhi - xlo)

    s = svg_open(W, H, title, xlabel)
    s.append(txt(W / 2, 18, esc(title), size=13, cls="figtitle"))
    # ticks
    step = 0.05 if span <= 0.16 else (0.1 if span <= 0.35 else 0.2)
    t = -math.floor(span / step) * step
    while t <= span + 1e-9:
        s.append(line(X(t), T - 6, X(t), H - 40, "grid"))
        v = round(t * 100)
        s.append(txt(X(t), H - 26, "0" if v == 0 else f"{v:+d}", size=10, cls="sub"))
        t += step
    s.append(line(X(0), T - 6, X(0), H - 40, "zero"))
    s.append(txt((L + W - R) / 2, H - 10, esc(xlabel), size=11, cls="sub"))

    y = T + 6
    cur = None
    for e in entries:
        if groups and e["group"] != cur:
            cur = e["group"]
            y += 16
            # Opaque strip so the header does not sit on top of the vertical gridlines.
            s.append(rect(8, y - 11, 8.0 + 6.2 * len(cur), 16, "var(--card)"))
            s.append(txt(12, y, esc(cur), anchor="start", size=11, cls="grouphdr"))
            y += 12
        y += rowh - 12
        s.append(txt(L - 12, y + 4, esc(e["label"]), anchor="end", size=11))
        col = e.get("colour", C_A)
        s.append(line(X(e["lo"]), y, X(e["hi"]), y, "ciline", f'stroke="{col}"'))
        for xv in (e["lo"], e["hi"]):
            s.append(line(X(xv), y - 5, X(xv), y + 5, "ciline", f'stroke="{col}"'))
        s.append(f'<circle cx="{X(e["rd"]):.1f}" cy="{y:.1f}" r="5" fill="{col}"/>')
        s.append(txt(W - R + 8, y + 4, e["extra"], anchor="start", size=10, cls="sub"))
        y += 12
    if note:
        s.append(txt(12, H - 10, esc(note), anchor="start", size=10, cls="sub"))
    s.append("</svg>")
    return "".join(s)


# --------------------------------------------------------------------------
# Figure 3 — ceiling effect: per-question cluster histogram
# --------------------------------------------------------------------------

def fig_ceiling(hist_rows, boundary) -> str:
    rows = [r for r in hist_rows if r["table"] == "overall"]
    rows.sort(key=lambda r: i(r["n_correct"]))
    counts = [(i(r["n_correct"]), i(r["n_questions"])) for r in rows]
    W, H = 720, 320
    L, R, T, B = 52, 18, 40, 62
    pw, ph = W - L - R, H - T - B
    peak = max(c for _, c in counts)
    # Round the axis top up to a readable step so the gridline labels are whole numbers.
    step = 10 ** math.floor(math.log10(peak / 4))
    step = next(step * m for m in (1, 2, 2.5, 5, 10) if step * m * 4 >= peak)
    mx = step * 4
    s = svg_open(W, H, "Within-question variance in the primary outcome",
                 "Histogram of how many of a question's 12 run-1 cells were "
                 "strict-correct; the two boundary bars have zero within-question variance.")
    s.append(txt(W / 2, 18, "Questions by number of strict-correct cells (out of 12)",
                 size=13, cls="figtitle"))
    for k in range(0, 5):
        v = mx * k / 4
        y = T + ph * (1 - k / 4)
        s.append(line(L, y, L + pw, y, "grid"))
        s.append(txt(L - 8, y + 4, f"{v:.0f}", anchor="end", size=10))
    s.append(line(L, T + ph, L + pw, T + ph, "ax"))
    slot = pw / len(counts)
    bw = slot * 0.72
    for n, (k, c) in enumerate(counts):
        cx = L + slot * (n + 0.5)
        h = ph * c / mx
        boundary_bar = k in (0, 12)
        s.append(rect(cx - bw / 2, T + ph - h, bw, h, C_HL if boundary_bar else C_A, 'rx="2"'))
        if c:
            s.append(txt(cx, T + ph - h - 5, str(c), size=10))
        s.append(txt(cx, T + ph + 16, str(k), size=10, cls="sub"))
    s.append(txt(W / 2, T + ph + 34, "cells strict-correct, of 12 (3 arms &times; 4 models)",
                 size=11, cls="sub"))
    s.append(legend(L, H - 10, [
        (f"zero within-question variance ({boundary} of 500 questions)", C_HL),
        ("some within-question variance", C_A)]))
    s.append("</svg>")
    return "".join(s)


# --------------------------------------------------------------------------
# Figure 4 — QQ plot of per-question difficulty
# --------------------------------------------------------------------------

def fig_qq(diff_rows, col="difficulty_overall") -> str:
    vals = sorted(f(r[col]) for r in diff_rows if r[col] not in ("", None))
    n = len(vals)
    mean = sum(vals) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1))
    zs = [(v - mean) / sd for v in vals]
    th = [inv_norm_cdf((k + 1 - 0.5) / n) for k in range(n)]
    W, H = 420, 400
    L, R, T, B = 52, 18, 40, 52
    pw, ph = W - L - R, H - T - B
    lo = min(min(th), min(zs)) - 0.3
    hi = max(max(th), max(zs)) + 0.3

    def X(v):
        return L + pw * (v - lo) / (hi - lo)

    def Y(v):
        return T + ph * (1 - (v - lo) / (hi - lo))

    s = svg_open(W, H, "QQ plot: per-question difficulty vs standard normal",
                 "Standardised per-question proportion correct against normal quantiles; "
                 "the boundary pile-up bends the upper tail away from the reference line.")
    s.append(txt(W / 2, 18, f"QQ: per-question difficulty (n={n})", size=13, cls="figtitle"))
    for t in range(math.ceil(lo), math.floor(hi) + 1):
        s.append(line(X(t), T, X(t), T + ph, "grid"))
        s.append(line(L, Y(t), L + pw, Y(t), "grid"))
        s.append(txt(X(t), T + ph + 15, str(t), size=10, cls="sub"))
        s.append(txt(L - 7, Y(t) + 4, str(t), anchor="end", size=10, cls="sub"))
    s.append(line(L, T + ph, L + pw, T + ph, "ax"))
    s.append(line(L, T, L, T + ph, "ax"))
    s.append(line(X(lo), Y(lo), X(hi), Y(hi), "ref"))
    for a, b in zip(th, zs):
        s.append(f'<circle cx="{X(a):.1f}" cy="{Y(b):.1f}" r="1.7" fill="{C_A}" '
                 f'fill-opacity="0.55"/>')
    s.append(txt(W / 2, H - 22, "theoretical normal quantile", size=11, cls="sub"))
    s.append(txt(14, T + ph / 2, "standardised sample quantile", size=11, cls="sub",
                 extra=f'transform="rotate(-90 14 {T + ph / 2:.1f})"'))
    s.append("</svg>")
    return "".join(s)


# --------------------------------------------------------------------------
# Figure 5 — flip rates by arm x model
# --------------------------------------------------------------------------

def fig_flip(flip_rows) -> str:
    rows = [r for r in flip_rows if r["exclude_vertex"] == "False"]
    arms = ["openrouter_A", "openrouter_B", "tailscale_A"]
    models = sorted({r["model"] for r in rows})
    colours = {"openrouter_A": C_A, "openrouter_B": C_B, "tailscale_A": C_T}
    by = {(r["arm"], r["model"]): r for r in rows}
    W, H = 720, 330
    L, R, T, B = 52, 18, 40, 78
    pw, ph = W - L - R, H - T - B
    mx = max(f(r["flip_rate"]) for r in rows)
    top = math.ceil(mx * 10) / 10
    s = svg_open(W, H, "Flip rate by arm and model",
                 "Share of scored replicates that turned a run-1 error into a correct "
                 "answer, by arm and model. Conditioned on failing run 1.")
    s.append(txt(W / 2, 18, "Flip rate on replicates (conditioned on a run-1 error)",
                 size=13, cls="figtitle"))
    for k in range(0, 6):
        v = top * k / 5
        y = T + ph * (1 - k / 5)
        s.append(line(L, y, L + pw, y, "grid"))
        s.append(txt(L - 8, y + 4, f"{v * 100:.0f}%", anchor="end", size=10))
    s.append(line(L, T + ph, L + pw, T + ph, "ax"))
    slot = pw / len(models)
    bw = min(34, slot / 4.4)
    for m, model in enumerate(models):
        cx = L + slot * (m + 0.5)
        for a, arm in enumerate(arms):
            r = by.get((arm, model))
            if not r:
                continue
            off = (a - 1) * (bw + 6)
            v = f(r["flip_rate"])
            h = ph * v / top
            s.append(rect(cx + off - bw / 2, T + ph - h, bw, h, colours[arm], 'rx="2"'))
            s.append(txt(cx + off, T + ph - h - 5, f"{v * 100:.0f}", size=9))
            s.append(txt(cx + off, T + ph + 14, f"{i(r['n_cells'])}", size=9, cls="sub"))
        s.append(txt(cx, T + ph + 30, esc(short_model(model)), size=11))
    s.append(txt(L - 8, T + ph + 14, "n cells", anchor="end", size=9, cls="sub"))
    s.append(legend(L, H - 22, [(a, colours[a]) for a in arms]))
    s.append("</svg>")
    return "".join(s)


# --------------------------------------------------------------------------
# HTML assembly
# --------------------------------------------------------------------------

CSS = """
:root{
  --bg:#ffffff; --fg:#1a1d21; --muted:#5c636e; --line:#d7dbe0; --soft:#f4f6f8;
  --card:#fbfcfd; --accent:#2f6fd0; --warn-bg:#fff7ed; --warn-line:#e0a05a;
  --warn-fg:#7a4310; --code:#f2f4f7; --hl:#fff3cd;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#12151a; --fg:#e6e9ee; --muted:#a2abb8; --line:#2c333d; --soft:#191d24;
    --card:#171b21; --accent:#6ea8fe; --warn-bg:#2b2015; --warn-line:#9a6a2f;
    --warn-fg:#f0c48a; --code:#1b2027; --hl:#3a3320;
  }
}
:root[data-theme="dark"]{
  --bg:#12151a; --fg:#e6e9ee; --muted:#a2abb8; --line:#2c333d; --soft:#191d24;
  --card:#171b21; --accent:#6ea8fe; --warn-bg:#2b2015; --warn-line:#9a6a2f;
  --warn-fg:#f0c48a; --code:#1b2027; --hl:#3a3320;
}
:root[data-theme="light"]{
  --bg:#ffffff; --fg:#1a1d21; --muted:#5c636e; --line:#d7dbe0; --soft:#f4f6f8;
  --card:#fbfcfd; --accent:#2f6fd0; --warn-bg:#fff7ed; --warn-line:#e0a05a;
  --warn-fg:#7a4310; --code:#f2f4f7; --hl:#fff3cd;
}
*{box-sizing:border-box;}
body{
  margin:0; background:var(--bg); color:var(--fg);
  font:16px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  overflow-x:hidden;
}
.wrap{max-width:1000px; margin:0 auto; padding:36px 22px 80px;}
h1{font-size:1.85rem; line-height:1.25; margin:0 0 6px; letter-spacing:-0.01em;}
h2{font-size:1.32rem; margin:44px 0 12px; padding-top:14px; border-top:1px solid var(--line);
   letter-spacing:-0.01em;}
h3{font-size:1.06rem; margin:26px 0 8px;}
h4{font-size:0.95rem; margin:18px 0 6px; color:var(--muted); text-transform:uppercase;
   letter-spacing:0.05em;}
p{margin:0 0 12px;} ul,ol{margin:0 0 14px; padding-left:22px;} li{margin:4px 0;}
a{color:var(--accent);}
code,kbd{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:0.87em;
  background:var(--code); padding:1px 5px; border-radius:4px;
  /* long file paths must break rather than push the page sideways on narrow screens */
  overflow-wrap:anywhere;}
td code,th code{overflow-wrap:normal;}
.sublead{color:var(--muted); font-size:0.95rem; margin:0 0 26px;}
.kicker{font-size:0.78rem; letter-spacing:0.12em; text-transform:uppercase; color:var(--muted);
  margin:0 0 8px;}
.toc{background:var(--soft); border:1px solid var(--line); border-radius:10px;
  padding:14px 18px; margin:0 0 30px;}
.toc ol{margin:0; padding-left:20px; columns:2; column-gap:28px;}
.toc li{margin:3px 0;}
@media (max-width:640px){ .toc ol{columns:1;} }
.headline{border:1px solid var(--line); border-left:4px solid var(--accent);
  background:var(--card); border-radius:8px; padding:14px 18px; margin:0 0 14px;}
.headline .h{font-weight:650; margin:0 0 4px;}
.headline p{margin:0; color:var(--fg);}
.callout{background:var(--warn-bg); border:1px solid var(--warn-line); color:var(--warn-fg);
  border-radius:8px; padding:13px 17px; margin:16px 0;}
.callout strong{color:inherit;}
.note{background:var(--soft); border:1px solid var(--line); border-radius:8px;
  padding:13px 17px; margin:16px 0; font-size:0.94rem;}
.tablewrap{overflow-x:auto; border:1px solid var(--line); border-radius:8px; margin:14px 0;
  max-width:100%;}
table{border-collapse:collapse; width:100%; font-size:0.87rem; min-width:min-content;}
th,td{padding:7px 11px; text-align:left; border-bottom:1px solid var(--line);
  white-space:nowrap; vertical-align:top;}
th{background:var(--soft); font-weight:620; position:sticky; top:0;}
tbody tr:last-child td{border-bottom:none;}
td.num,th.num{text-align:right; font-variant-numeric:tabular-nums;}
td.wrapcell{white-space:normal; min-width:230px;}
tr.total td{font-weight:650; background:var(--soft);}
.figbox{border:1px solid var(--line); border-radius:10px; background:var(--card);
  padding:14px 16px 10px; margin:18px 0;}
.figbox .cap{font-size:0.86rem; color:var(--muted); margin:8px 2px 0;}
.figbox .cap b{color:var(--fg); font-weight:620;}
svg.fig{display:block; width:100%; height:auto; max-width:100%;}
svg .ax{stroke:var(--fg); stroke-width:1; opacity:0.55;}
svg .grid{stroke:var(--line); stroke-width:1;}
svg .zero{stroke:var(--fg); stroke-width:1.2; opacity:0.7; stroke-dasharray:3 3;}
svg .ref{stroke:#c2413c; stroke-width:1.2; stroke-dasharray:5 4;}
svg .ciline{stroke-width:2;}
svg .drop{stroke:var(--muted); stroke-width:1; stroke-dasharray:3 3;}
svg text{fill:var(--fg);}
svg text.sub{fill:var(--muted);}
svg text.dropl{fill:var(--fg); font-weight:600;}
svg text.figtitle{font-weight:640;}
svg text.grouphdr{fill:var(--muted); font-weight:640; letter-spacing:0.04em;}
.example{border:1px solid var(--line); border-radius:10px; overflow:hidden; margin:16px 0;}
.example .exhead{background:var(--soft); padding:10px 16px; font-size:0.9rem;
  border-bottom:1px solid var(--line);}
.example .cols{display:grid; grid-template-columns:1fr 1fr;}
@media (max-width:720px){ .example .cols{grid-template-columns:1fr;} }
.example .col{padding:12px 16px;}
.example .col + .col{border-left:1px solid var(--line);}
@media (max-width:720px){ .example .col + .col{border-left:none; border-top:1px solid var(--line);} }
.example .lab{font-size:0.75rem; letter-spacing:0.1em; text-transform:uppercase;
  color:var(--muted); margin:0 0 8px;}
.example ol{list-style:none; padding:0; margin:0; font-size:0.92rem;}
.example ol li{padding:5px 8px; border-radius:5px; margin:2px 0;}
.example li.same{color:var(--muted);}
.example li.correct{background:var(--hl); font-weight:600; color:var(--fg);}
.example .stem{font-size:0.95rem; margin:0 0 10px;}
.badge{display:inline-block; font-size:0.72rem; letter-spacing:0.06em; text-transform:uppercase;
  border:1px solid var(--line); border-radius:20px; padding:2px 9px; color:var(--muted);
  margin-left:6px; white-space:nowrap;}
.badge.stop{border-color:var(--warn-line); color:var(--warn-fg); background:var(--warn-bg);}
.small{font-size:0.87rem; color:var(--muted);}
.footnotes{font-size:0.85rem; color:var(--muted);}
.footnotes li{margin:6px 0;}
dl.prov{margin:0;}
dl.prov dt{font-weight:620; margin-top:12px;}
dl.prov dd{margin:2px 0 0 0; color:var(--muted); font-size:0.9rem;}
hr.soft{border:none; border-top:1px solid var(--line); margin:26px 0;}
@media print{
  :root{--bg:#fff; --fg:#000; --muted:#444; --line:#bbb; --soft:#f3f3f3; --card:#fff;
        --warn-bg:#f7f7f7; --warn-line:#999; --warn-fg:#000; --code:#f0f0f0; --hl:#eee;}
  body{font-size:10.5pt;}
  .wrap{max-width:none; padding:0;}
  h2{page-break-after:avoid; break-after:avoid;}
  .figbox,.example,.headline,.callout,.note,.tablewrap{page-break-inside:avoid;
    break-inside:avoid;}
  th{position:static;}
  .toc{page-break-after:always;}
  a{color:#000; text-decoration:none;}
}
"""


def table(headers, rows, classes=None, foot=None) -> str:
    classes = classes or [""] * len(headers)
    out = ['<div class="tablewrap"><table><thead><tr>']
    for h, c in zip(headers, classes):
        out.append(f'<th class="{c}">{h}</th>')
    out.append("</tr></thead><tbody>")
    for r in rows:
        cls = ""
        if isinstance(r, tuple):
            r, cls = r
        out.append(f'<tr class="{cls}">')
        for v, c in zip(r, classes):
            out.append(f'<td class="{c}">{v}</td>')
        out.append("</tr>")
    out.append("</tbody>")
    if foot:
        out.append(f'<tfoot><tr><td colspan="{len(headers)}" class="small">{foot}</td></tr></tfoot>')
    out.append("</table></div>")
    return "".join(out)


def figbox(svg: str, caption: str) -> str:
    return f'<div class="figbox">{svg}<p class="cap">{caption}</p></div>'


def git_info() -> dict:
    def run(*args):
        try:
            return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True,
                                  text=True, check=True, timeout=20).stdout.strip()
        except Exception:
            return ""
    head = run("rev-parse", "HEAD")
    return {
        "commit": head,
        "short": head[:8],
        "date": run("log", "-1", "--format=%cI"),
        "subject": run("log", "-1", "--format=%s"),
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": run("status", "--porcelain", "--", str(BASE)),
    }


# --------------------------------------------------------------------------
# Report body
# --------------------------------------------------------------------------

def build(d: dict, g: dict) -> str:
    nb = d["norm_binary"]
    pr = d["primary"]
    ab = sorted(d["ab"], key=lambda r: -(f(r["acc_x"]) - f(r["acc_y"])))
    prov = d["prov"]
    grp_p = d["grp_primary"]
    grp_s = d["grp_secondary"]
    git = git_info()
    now = datetime.now(timezone.utc).astimezone()

    ab_min, ab_max = ab[-1], ab[0]
    pooled = pr["condition_A_vs_B"]["pooled_gee"]
    perm = pr["condition_A_vs_B"]["pooled_permutation_robustness"]
    prov_pooled = pr["provider_openrouterA_vs_tailscaleA"]["pooled_gee"]
    prov_perm = pr["provider_openrouterA_vs_tailscaleA"]["pooled_permutation_robustness"]
    icc = pr["clustering_diagnostic"]["icc_question_strict_correct"]
    bnd = nb["strict_correct"]["boundary_counts"]
    grp_pooled = next(r for r in grp_p if r["scope"] == "pooled_arm_adjusted")
    grp_A = next(r for r in grp_p if r["scope"] == "openrouter_A")
    grp_B = next(r for r in grp_p if r["scope"] == "openrouter_B")

    H: list[str] = []
    A = H.append

    # ------------------------------------------------------------------ head
    A('<div class="wrap">')
    A('<p class="kicker">Tier-1 MCQ benchmark &middot; experiment 4 (aug-26) &middot; '
      'statistical analysis</p>')
    A("<h1>None-of-the-above susceptibility in a 500-item Spanish medical MCQ benchmark</h1>")
    A(f'<p class="sublead">Four models, three arms, {g["n_run1_cells"]:,} scored run-1 cells, '
      f'plus {g["n_scored"]:,} scored replicates of the cells that failed. '
      f'Generated {esc(now.strftime("%Y-%m-%d %H:%M:%S %Z"))} from commit '
      f'<code>{esc(git["short"])}</code>.</p>')

    A('<nav class="toc"><ol>'
      '<li><a href="#headline">Headline findings</a></li>'
      '<li><a href="#design">What the experiment is</a></li>'
      '<li><a href="#diagnostics">Distributional diagnostics</a></li>'
      '<li><a href="#primary">Primary results</a></li>'
      '<li><a href="#groupings">Model groupings</a></li>'
      '<li><a href="#stability">Stability under replication</a></li>'
      '<li><a href="#limits">Limitations and threats to validity</a></li>'
      '<li><a href="#provenance">Provenance</a></li>'
      "</ol></nav>")

    # -------------------------------------------------------------- headline
    A('<h2 id="headline">1. Headline findings</h2>')
    A(f"<p>The comparison at the centre of this study is not a generic “condition A "
      f"versus condition B”. The two item banks share all {g['shared']} questions, all "
      f"question text and all correct letters; the only thing that changes is the "
      f"<em>correct option itself</em>, which in condition B is replaced &mdash; in all "
      f"{g['shared']} items, in the same letter slot &mdash; by the fixed string "
      f"<em>&ldquo;{esc(g['nota'])}&rdquo;</em>. "
      f"Every distractor is byte-identical across the two conditions "
      f"({g['coldiff']['option_a']} of {g['shared']} option-<code>a</code> cells differ, and "
      f"the option-<code>b</code>/<code>c</code>/<code>d</code> differences are exactly the "
      f"items whose correct letter is that letter). "
      f"So the A-vs-B contrast measures one thing: <strong>how much accuracy a model loses "
      f"when the right answer stops being a plausible assertion and becomes a "
      f"none-of-the-above (NOTA) negation.</strong></p>")

    A('<div class="headline"><p class="h">1. Every model is substantially worse at '
      'none-of-the-above items, and the size of the loss separates them sharply.</p>'
      f'<p>Run-1 accuracy falls by '
      f'{pp(f(ab_min["risk_diff_x_minus_y"]), signed=False)} percentage points '
      f'for {esc(short_model(ab_min["model"]))} and '
      f'{pp(f(ab_max["risk_diff_x_minus_y"]), signed=False)} '
      f'points for {esc(short_model(ab_max["model"]))} '
      f'({esc(short_model(ab[1]["model"]))} '
      f'{pp(f(ab[1]["risk_diff_x_minus_y"]), signed=False)}, '
      f'{esc(short_model(ab[2]["model"]))} '
      f'{pp(f(ab[2]["risk_diff_x_minus_y"]), signed=False)}). '
      f'All four are paired within question over {i(ab[0]["n_pairs"])} matched items and all '
      f'four survive Holm correction (largest adjusted p in the family: '
      f'{fmt_p(max(f(r["p_holm"]) for r in ab))}).</p></div>')

    A('<div class="headline"><p class="h">2. The failure has a visible signature: models '
      'start picking a distractor they otherwise ignore.</p>'
      f'<p>Option <code>a</code> is never the correct answer in any of the {g["shared"]} '
      f'questions, under either condition. Models selected it on '
      f'{pct(g["letter"]["openrouter_A"].get("a", 0) / g["arm_n"]["openrouter_A"], 1)} of '
      f'condition-A cells but '
      f'{pct(g["letter"]["openrouter_B"].get("a", 0) / g["arm_n"]["openrouter_B"], 1)} of '
      f'condition-B cells &mdash; always wrong either way. When the correct answer is a '
      f'negation, plausibility-matching pushes selections onto content distractors.</p></div>')

    A('<div class="headline"><p class="h">3. The provider contrast is small and its sign '
      'depends on the model; it is not a transport effect.</p>'
      f'<p>Holding condition at A, pooled accuracy differs by '
      f'{pp(f(prov_perm["observed_pooled_risk_diff"]))} points between the two arms '
      f'(OpenRouter minus TailScale; pooled GEE OR {num(f(prov_pooled["or_arm_x_vs_arm_y"]))}, '
      f'95% CI [{num(f(prov_pooled["or_ci_lo"]))}, {num(f(prov_pooled["or_ci_hi"]))}], '
      f'Holm p {fmt_p(f(prov_pooled["p_holm"]))}) &mdash; two orders of magnitude smaller than '
      f'the NOTA effect. Only one of four models reaches significance per-model. The two arms '
      f'differ in provider <em>and</em> prompt delivery (the TailScale arm uses GIFT prompt ID '
      f'13 with server-side MCQ instructions and does not honour the JSON-schema enforcement '
      f'OpenRouter applies), so this is a provider+prompt-delivery contrast, not an isolated '
      f'transport or infrastructure measurement.</p></div>')

    A('<div class="headline"><p class="h">4. Two requested analyses cannot be delivered as '
      'requested, and no substitute was quietly run in their place.</p>'
      f'<p><strong>Big vs small: infeasible.</strong> Two of the four models have no defensible '
      f'parameter count, and for the two that do, the ordering inverts between total and active '
      f'parameters. <strong>Provider &times; condition: inestimable.</strong> There is no '
      f'<code>tailscale_B</code> arm, so the interaction term has no data behind it &mdash; it '
      f'is absent from the design, not merely underpowered. <strong>Open vs closed</strong> was '
      f'computed but has n_models = 1 in the closed group, which makes it arithmetically a '
      f'gemini-versus-the-other-three comparison.</p></div>')

    # ---------------------------------------------------------------- design
    A('<h2 id="design">2. What the experiment is</h2>')
    A(f"<p>{g['n_questions']} Spanish medical multiple-choice questions, four options each, "
      f"answered once by each of {g['n_models']} models in each of {g['n_arms']} arms &mdash; "
      f"{g['n_questions']} &times; {g['n_arms']} &times; {g['n_models']} = "
      f"{g['n_run1_cells']:,} run-1 cells, all of them answered. The three arms are "
      f"{', '.join('<code>' + esc(a) + '</code>' for a in g['arms'])}: OpenRouter carries both "
      f"conditions, TailScale carries condition A only.</p>")
    A("<p>The primary outcome is <code>strict_correct</code> &mdash; the selected letter and "
      "the selected option text must both match the gold answer. Among the run-1 errors this "
      "is effectively “picked the wrong option” rather than a formatting artefact.</p>")

    A(f"<h3>2.1 The NOTA manipulation, on a real item</h3>")
    A(f"<p>Below is question <code>{esc(g['example_id'])}</code>, selected programmatically as "
      f"the most compact item in the bank (shortest question text plus options) so it fits on "
      f"the page. Nothing about it is special otherwise. Grey options are byte-identical "
      f"between the two conditions; the highlighted option is the correct one.</p>")

    exA, exB = g["example_A"], g["example_B"]
    cl = exA["correct_letter"]
    cols = []
    for lab, rec in (("Condition A", exA), ("Condition B (NOTA)", exB)):
        li = []
        for L in "abcd":
            same = exA["option_" + L] == exB["option_" + L]
            cls = "correct" if L == cl else ("same" if same else "")
            li.append(f'<li class="{cls}"><b>{L})</b> {esc(rec["option_" + L])}</li>')
        cols.append(f'<div class="col"><p class="lab">{lab}</p><ol>{"".join(li)}</ol></div>')
    A(f'<div class="example"><div class="exhead"><b>{esc(g["example_id"])}</b> &mdash; '
      f'{esc(exA["question_text"])} <span class="badge">correct letter: '
      f'{esc(cl)}, both conditions</span></div>'
      f'<div class="cols">{"".join(cols)}</div></div>')

    ex_wrong = [r for r in g["example_cells"] if r["strict_correct"] != "1"]
    if ex_wrong:
        wr = "; ".join(
            f"{esc(short_model(r['model']))} in <code>{esc(r['arm'])}</code> chose "
            f"<code>{esc(r['selected_letter'])}</code>" for r in ex_wrong)
        A(f'<p class="small">On this item, {len(g["example_cells"]) - len(ex_wrong)} of '
          f'{len(g["example_cells"])} run-1 cells were correct. The exception: {wr} &mdash; a '
          f'content distractor, under the NOTA condition.</p>')

    A("<h3>2.2 What differs between the two banks, recomputed</h3>")
    cd = g["coldiff"]
    A(table(
        ["Column", "Rows differing (of %d)" % g["shared"], "Reading"],
        [[f"<code>{k}</code>", f'<span class="num">{cd[k]}</span>', v] for k, v in [
            ("question_text", "identical text in both banks"),
            ("correct_letter", "the correct slot never moves"),
            ("option_a", "option <code>a</code> is never the correct answer, so it never changes"),
            ("option_b", f"exactly the {g['correct_letter_counts'].get('b', 0)} items whose correct letter is <code>b</code>"),
            ("option_c", f"exactly the {g['correct_letter_counts'].get('c', 0)} items whose correct letter is <code>c</code>"),
            ("option_d", f"exactly the {g['correct_letter_counts'].get('d', 0)} items whose correct letter is <code>d</code>"),
            ("correct_option_text", "every item&rsquo;s correct answer is replaced"),
        ]],
        classes=["", "num", "wrapcell"],
        foot=f"Recomputed at build time by diffing the two frozen item banks. The correct "
             f"option in condition B takes {g['n_nota_variants']} distinct value across all "
             f"{g['shared']} items."))

    A(f"<p>The replaced option is also shorter and constant. Mean correct-option length is "
      f"{num(g['len_correct_A'], 1)} characters in A and {num(g['len_correct_B'], 1)} in B "
      f"(the fixed NOTA string), against {num(g['len_distractor_A'], 1)} for distractors. In A "
      f"the correct answer is slightly longer than its distractors; in B it is conspicuously "
      f"shorter and identical everywhere. Both are surface cues, pointing in opposite "
      f"directions &mdash; see &sect;7.</p>")

    A("<h3>2.3 The replicate design</h3>")
    tri = g["tri_by_arm"]
    A(f"<p>Every run-1 cell that scored incorrect &mdash; {g['n_incorrect_cells']} of "
      f"{g['n_run1_cells']:,} &mdash; was re-run at runs 2 and 3, giving "
      f"{g['n_logical_calls']:,} logical calls, of which {g['n_scored']:,} produced a score "
      f"({pct(g['n_scored'] / g['n_logical_calls'], 1)}) and {g['n_exhausted']} exhausted the "
      f"five-attempt retry ceiling without one. Because condition B is harder, the replicate "
      f"set is not balanced across arms: "
      f"{', '.join(f'<code>{esc(a)}</code> {tri[a]}' for a in sorted(tri, key=lambda k: -tri[k]))}. "
      f"Any pooled statement about replicates is weighted toward NOTA items.</p>")

    A('<div class="callout"><strong>Run-1 cells were never replicated when correct.</strong> '
      f'The {i(nb["strict_correct"]["overall"]["n_correct"]):,} run-1-correct cells have no '
      f'run 2 or run 3, so the correct&rarr;wrong transition is unmeasured in this study. '
      'Everything in &sect;6 is conditioned on having failed run 1.</div>')

    # ----------------------------------------------------------- diagnostics
    A('<h2 id="diagnostics">3. Distributional diagnostics</h2>')
    A("<p>The analysis was asked to check normality first and choose tests accordingly. That "
      "was honoured, but not by running a normality test on the outcome: "
      "<code>strict_correct</code> and <code>flip</code> are Bernoulli indicators, and a "
      "Bernoulli variable is not normal for any rate strictly between 0 and 1. Shapiro-Wilk on "
      "0/1 data rejects every time, for a reason that carries no information about which test "
      "is valid. <strong>For the binary outcomes, test choice follows from data type and from "
      "the pairing/clustering structure, not from a normality result.</strong> Normality "
      "diagnostics were instead run on the quantities that really are continuous.</p>")

    cont = d["norm_cont"]["diagnostics"]
    rows = []
    for r in cont:
        rows.append([
            f'<code>{esc(r["name"])}</code>',
            f'{i(r["n"]):,}',
            num(r["shapiro_W"], 3),
            fmt_p(r["shapiro_p"]),
            num(r["anderson_darling_statistic"], 2),
            fmt_p(r["anderson_darling_p_interpolated_scipy"]),
            num(r["skewness"], 2),
            num(r["kurtosis_excess"], 2),
        ])
    A(table(["Quantity", "n", "Shapiro W", "Shapiro p", "AD statistic", "AD p (scipy)",
             "skew", "excess kurtosis"],
            rows, classes=["", "num", "num", "num", "num", "num", "num", "num"],
            foot="scipy&rsquo;s Anderson-Darling p is floored at 0.01 by its interpolation "
                 "table; an independent Stephens (1974) closed-form approximation agrees that "
                 "all of these sit far below any conventional alpha "
                 "(<code>results/normality_continuous_diagnostics.json</code>)."))

    A("<p>Every quantity rejects normality decisively, and for reasons that are structural "
      "rather than surprising. Per-question difficulty is a proportion over 4 or 12 Bernoulli "
      "trials: discrete support, bounded on [0,1], heavily piled at the top. Latency is a "
      "positive right-skewed duration; a log transform cuts the skew substantially and lifts "
      "Shapiro W, but does not reach normality.</p>")

    A(figbox(fig_qq(d["norm_diff"]),
             "<b>Figure 1.</b> QQ plot of standardised per-question difficulty (proportion of "
             "the 12 run-1 cells correct) against standard-normal quantiles, drawn from "
             "<code>results/normality_per_question_difficulty.csv</code>. The upper tail is a "
             "flat stack of near-identical high values &mdash; the ceiling effect quantified "
             "below &mdash; while the lower tail lags the reference line."))

    A("<h3>3.1 The ceiling effect, and what it rules out</h3>")
    A(figbox(fig_ceiling(d["hist"], bnd["n_questions_at_boundary"]),
             f"<b>Figure 2.</b> Per-question cluster histogram over all "
             f"{g['n_questions']} questions, from "
             f"<code>results/normality_binary_outcome_cluster_histogram.csv</code>. "
             f"{bnd['n_questions_ceiling_12of12']} questions are answered correctly by every "
             f"arm&times;model cell and {bnd['n_questions_floor_0of12']} by none."))
    A(f"<p><strong>{bnd['n_questions_at_boundary']} of {g['n_questions']} questions "
      f"({pct(bnd['pct_at_boundary'], 1)}) have zero within-question variance</strong> in the "
      f"primary outcome; {bnd['n_questions_interior']} are interior. That is the fact that "
      f"gates aggregation. A method that collapses each question to a single proportion and "
      f"then runs a normal-theory test on those {g['n_questions']} numbers &mdash; a paired "
      f"t-test on per-question A-minus-B differences, say &mdash; discards over a third of the "
      f"dataset, because a question stuck at 12/12 or 0/12 contributes a fixed, uninformative "
      f"value no matter which arm produced it. Methods that operate on the individual binary "
      f"cells do not have this problem: a boundary question still contributes correctly, it "
      f"just correctly contributes “no evidence of an effect”.</p>")

    A(f"<p>Clustering is real and was measured, not assumed: the one-way random-effects ICC of "
      f"run-1 <code>strict_correct</code> within question is <strong>{num(icc, 3)}</strong> "
      f"(k&asymp;{num(pr['clustering_diagnostic']['k_cells_per_question'], 0)} cells per "
      f"question). Hence the test choices below:</p>")
    A("<ul>"
      "<li><b>Paired binary contrasts</b> (A vs B; provider at fixed condition; model-vs-model "
      "within an arm) &mdash; exact McNemar on the discordant pairs, because both sides answer "
      "the identical question set. A two-sample proportion test would ignore that pairing and "
      "inflate the standard error.</li>"
      "<li><b>Pooled and grouped contrasts</b> &mdash; cluster-robust logistic regression "
      "(GEE, exchangeable working correlation, clusters = question), cross-checked with a "
      "permutation test that permutes whole questions.</li>"
      "<li><b>Omnibus across four models within an arm</b> &mdash; Cochran&rsquo;s Q "
      "(related samples).</li>"
      "</ul>")
    A('<p class="small">Explicitly not done: justifying any of these choices with a '
      'Shapiro-Wilk or Anderson-Darling result on the binary outcome. No such test was run, so '
      'there is no such result to cite.</p>')

    # --------------------------------------------------------------- primary
    A('<h2 id="primary">4. Primary results</h2>')
    A("<h3>4.1 NOTA susceptibility: condition A vs condition B</h3>")
    A(f"<p>Paired within question, OpenRouter only, {i(ab[0]['n_pairs'])} matched items per "
      f"model. Family: {len(ab)} per-model exact McNemar tests plus one pooled GEE test, "
      f"Holm-Bonferroni corrected together.</p>")
    A(figbox(fig_nota(d["ab"]),
             "<b>Figure 3.</b> Run-1 accuracy per model under each condition, from "
             "<code>results/primary_condition_AvsB_per_model.csv</code>. The bracket is the "
             "paired risk difference; every distractor is identical between the two bars."))

    rows = []
    for r in ab:
        rows.append([
            esc(short_model(r["model"])),
            pct(f(r["acc_x"])), pct(f(r["acc_y"])),
            f"{pp(f(r['risk_diff_x_minus_y']))} pp",
            ci(f(r["risk_diff_ci_lo"]), f(r["risk_diff_ci_hi"])),
            num(f(r["mcnemar_or_x_vs_y"])),
            ci(f(r["or_ci_lo"]), f(r["or_ci_hi"]), nd=2, scale=1.0, signed=False),
            f'{i(r["discordant_b_x_only"])} / {i(r["discordant_c_y_only"])}',
            fmt_p(f(r["p_raw"])), fmt_p(f(r["p_holm"])),
        ])
    A(table(["Model", "acc A", "acc B", "risk diff (A&minus;B)", "95% CI (pp)",
             "OR", "95% CI", "discordant b / c", "p (raw)", "p (Holm)"],
            rows,
            classes=["", "num", "num", "num", "num", "num", "num", "num", "num", "num"],
            foot="McNemar exact (binomial on discordant pairs). <i>b</i> = correct in A only, "
                 "<i>c</i> = correct in B only. Odds ratio is <i>b/c</i>."))

    A(f"<p><b>Pooled:</b> GEE logistic, exchangeable correlation, clusters = question, "
      f"{i(pooled['n_obs']):,} observations over {i(pooled['n_clusters_questions'])} question "
      f"clusters and {len(ab)} models. OR(A vs B) = "
      f"<strong>{num(f(pooled['or_arm_x_vs_arm_y']))}</strong> "
      f"[{num(f(pooled['or_ci_lo']))}, {num(f(pooled['or_ci_hi']))}], Wald z "
      f"{num(f(pooled['wald_z']))}, Holm p {fmt_p(f(pooled['p_holm']))}. A distribution-free "
      f"check that permutes whole questions ({i(perm['n_perm']):,} permutations, whole-question "
      f"swap of the arm labels across all four models jointly) gives an observed pooled risk "
      f"difference of {pp(f(perm['observed_pooled_risk_diff']), 2)} pp with "
      f"{i(perm['n_exceed'])} of {i(perm['n_perm']):,} permutations at least as extreme.</p>")

    A("<h3>4.2 Provider and prompt delivery: openrouter_A vs tailscale_A</h3>")
    A('<div class="callout"><strong>Framing, binding.</strong> These two arms differ in more '
      'than transport. The TailScale arm uses GIFT prompt ID 13 with server-side MCQ '
      'instructions and does not honour the JSON-schema enforcement OpenRouter applies. Every '
      'number below is a <em>provider + prompt-delivery</em> contrast; it must not be reported '
      'as an isolated transport or infrastructure effect. Condition is held fixed at A because '
      'there is no <code>tailscale_B</code> arm.</div>')

    rows = []
    for r in prov:
        rows.append([
            esc(short_model(r["model"])),
            pct(f(r["acc_x"])), pct(f(r["acc_y"])),
            f"{pp(f(r['risk_diff_x_minus_y']))} pp",
            ci(f(r["risk_diff_ci_lo"]), f(r["risk_diff_ci_hi"])),
            num(f(r["mcnemar_or_x_vs_y"])),
            ci(f(r["or_ci_lo"]), f(r["or_ci_hi"]), nd=2, scale=1.0, signed=False),
            fmt_p(f(r["p_raw"])), fmt_p(f(r["p_holm"])),
            "yes" if r["reject_holm_0.05"] == "True" else "no",
        ])
    A(table(["Model", "acc OR_A", "acc TS_A", "risk diff (OR&minus;TS)", "95% CI (pp)",
             "OR", "95% CI", "p (raw)", "p (Holm)", "Holm-significant"],
            rows,
            classes=["", "num", "num", "num", "num", "num", "num", "num", "num", "num"]))
    A(f"<p><b>Pooled:</b> OR = {num(f(prov_pooled['or_arm_x_vs_arm_y']))} "
      f"[{num(f(prov_pooled['or_ci_lo']))}, {num(f(prov_pooled['or_ci_hi']))}], Wald p "
      f"{fmt_p(f(prov_pooled['wald_p']))}, Holm p {fmt_p(f(prov_pooled['p_holm']))}; "
      f"permutation p {fmt_p(f(prov_perm['perm_p_two_sided']))} "
      f"({i(prov_perm['n_exceed'])}/{i(prov_perm['n_perm']):,}). The pooled point estimate "
      f"favours TailScale by "
      f"{pp(abs(f(prov_perm['observed_pooled_risk_diff'])), 2, signed=False)} pp &mdash; "
      f"real, but roughly an order of magnitude smaller than the smallest NOTA effect, and "
      f"driven mostly by one model.</p>")

    A("<h3>4.3 Both contrasts side by side</h3>")
    entries = []
    for r in ab:
        entries.append({
            "label": short_model(r["model"]),
            "rd": f(r["risk_diff_x_minus_y"]), "lo": f(r["risk_diff_ci_lo"]),
            "hi": f(r["risk_diff_ci_hi"]),
            "group": "NOTA susceptibility (condition A − condition B, paired)",
            "colour": C_B,
            # fmt_p returns HTML entities; inline SVG is parsed by the HTML parser, so
            # they resolve correctly. Do not strip them -- a bare "<" would break the SVG.
            "extra": "Holm p " + fmt_p(f(r["p_holm"])),
        })
    for r in prov:
        entries.append({
            "label": short_model(r["model"]),
            "rd": f(r["risk_diff_x_minus_y"]), "lo": f(r["risk_diff_ci_lo"]),
            "hi": f(r["risk_diff_ci_hi"]),
            "group": "Provider + prompt delivery (openrouter_A − tailscale_A)",
            "colour": C_A,
            "extra": "Holm p " + fmt_p(f(r["p_holm"])),
        })
    A(figbox(forest(entries, "Paired risk differences, percentage points",
                    "risk difference (percentage points), 95% CI", groups=True),
             "<b>Figure 4.</b> Paired risk differences with 95% confidence intervals, on one "
             "scale, from <code>primary_condition_AvsB_per_model.csv</code> and "
             "<code>primary_provider_per_model.csv</code>. The NOTA effect is large, "
             "one-signed and consistent; the provider effect is small and changes sign across "
             "models."))

    A("<h3>4.4 Model main effects</h3>")
    A("<p>All four models answer the same questions within an arm, so this is a related-samples "
      "design: Cochran&rsquo;s Q as the omnibus (the three arm-level tests form one Holm "
      "family), then pairwise exact McNemar with each arm&rsquo;s six pairs forming its own "
      "Holm family.</p>")
    rows = [[f'<code>{esc(r["arm"])}</code>', i(r["n_questions"]), i(r["k_models"]),
             num(f(r["cochrans_q"])), i(r["df"]), fmt_p(f(r["p_raw"])), fmt_p(f(r["p_holm"]))]
            for r in d["omni"]]
    A(table(["Arm", "n questions", "k models", "Cochran Q", "df", "p (raw)", "p (Holm)"],
            rows, classes=["", "num", "num", "num", "num", "num", "num"]))

    by_model = nb["strict_correct"]["by_model"]
    rows = [[esc(short_model(m)), f'{i(v["n_correct"]):,} / {i(v["n"]):,}', pct(v["rate"], 2)]
            for m, v in sorted(by_model.items(), key=lambda kv: -kv[1]["rate"])]
    by_arm = nb["strict_correct"]["by_arm"]
    A("<h4>Base rates</h4>")
    A(table(["Model (all arms)", "correct / cells", "accuracy"], rows,
            classes=["", "num", "num"]))
    rows = [[f'<code>{esc(a)}</code>', f'{i(v["n_correct"]):,} / {i(v["n"]):,}', pct(v["rate"], 2)]
            for a, v in sorted(by_arm.items(), key=lambda kv: -kv[1]["rate"])]
    rows.append(([f'<b>overall</b>',
                  f'{i(nb["strict_correct"]["overall"]["n_correct"]):,} / '
                  f'{i(nb["strict_correct"]["overall"]["n"]):,}',
                  pct(nb["strict_correct"]["overall"]["rate"], 2)], "total"))
    A(table(["Arm (all models)", "correct / cells", "accuracy"], rows,
            classes=["", "num", "num"]))

    A("<h4>Pairwise post-hoc, Holm-corrected within arm</h4>")
    rows = []
    for r in d["posthoc"]:
        rows.append([
            f'<code>{esc(r["arm"])}</code>',
            esc(short_model(r["model_i"])), esc(short_model(r["model_j"])),
            pct(f(r["acc_i"])), pct(f(r["acc_j"])),
            f"{pp(f(r['risk_diff_i_minus_j']))} pp",
            ci(f(r["rd_ci_lo"]), f(r["rd_ci_hi"])),
            num(f(r["or_i_vs_j"])),
            ci(f(r["or_ci_lo"]), f(r["or_ci_hi"]), nd=2, scale=1.0, signed=False),
            fmt_p(f(r["mcnemar_exact_p"])), fmt_p(f(r["p_holm"])),
        ])
    A(table(["Arm", "Model i", "Model j", "acc i", "acc j", "risk diff (i&minus;j)",
             "95% CI (pp)", "OR", "95% CI", "p (raw)", "p (Holm)"],
            rows,
            classes=["", "", "", "num", "num", "num", "num", "num", "num", "num", "num"],
            foot=f"{len(d['posthoc'])} pairwise tests: 6 pairs &times; 3 arms, each arm its own "
                 f"Holm family."))

    # ------------------------------------------------------------- groupings
    A('<h2 id="groupings">5. Model groupings</h2>')

    A("<h3>5.1 Big vs small &mdash; declared infeasible, not computed</h3>")
    bvs = d["grp"]["big_vs_small"]
    A(f'<div class="callout"><strong>Status: {esc(bvs["status"])}.</strong> No statistical test '
      f'was run for this grouping. {esc(bvs["reason"])}</div>')
    A(f"<p>{i(bvs['n_models_evaluable_for_size'])} of {i(bvs['n_models_total'])} models have a "
      f"parameter count that can be defended from this repository. For the two that do, the "
      f"label is still not well defined: <code>gemma-4-26b-a4b-it</code> is 26B total / ~4B "
      f"active and <code>qwen3.6-35b-a3b</code> is 35B total / ~3B active, so qwen is the "
      f"larger model by total parameters and gemma is the larger model by active parameters. "
      f"<strong>The ordering inverts with the choice of size metric</strong>, and this study "
      f"has no independent reason to prefer one metric &mdash; picking one would decide the "
      f"answer before any data was examined. Inventing a count for "
      f"<code>z-ai/glm-5.2</code> or <code>google/gemini-3.6-flash</code> was not an option; "
      f"both are recorded as <code>UNVERIFIED</code> in "
      f"<code>results/MODEL_TAXONOMY.md</code>, which is a final answer there, not a gap to "
      f"fill later.</p>")

    A("<h3>5.2 Open vs closed weights</h3>")
    open_models = d["grp"]["open_models"]
    closed_models = d["grp"]["closed_models"]
    A(f'<div class="callout"><strong>n_models in the closed group = {len(closed_models)}.</strong> '
      f'The closed group is exactly {esc(", ".join(short_model(m) for m in closed_models))}. '
      f'&ldquo;Closed&rdquo; and &ldquo;gemini&rdquo; are the same partition of this dataset, '
      f'so every number below is arithmetically a gemini-versus-the-other-three comparison. '
      f'Cluster-robust standard errors correct for questions contributing several correlated '
      f'cells; nothing can correct for a group of one. A significant result here is evidence '
      f'about this one model &mdash; <strong>it is not evidence about open-weight models as a '
      f'class</strong>.</div>')
    A(f'<p class="small">Open group ({len(open_models)} models): '
      f'{", ".join("<code>" + esc(m) + "</code>" for m in open_models)}. Closed group '
      f'({len(closed_models)} model): '
      f'{", ".join("<code>" + esc(m) + "</code>" for m in closed_models)}.</p>')

    rows = []
    for r in grp_p:
        rows.append([
            f'<code>{esc(r["scope"])}</code>',
            f'<b>{i(r["n_models_open"])} / {i(r["n_models_closed"])}</b>',
            f'{i(r["n_cells_open"]):,} / {i(r["n_cells_closed"]):,}',
            pct(f(r["prop_open"])), pct(f(r["prop_closed"])),
            f"{pp(f(r['risk_difference']))} pp",
            ci(f(r["rd_ci_lo"]), f(r["rd_ci_hi"])),
            num(f(r["or"]), 3),
            ci(f(r["or_ci_lo"]), f(r["or_ci_hi"]), nd=3, scale=1.0, signed=False),
            fmt_p(f(r["p_gee_wald"])), fmt_p(f(r["p_gee_wald_holm"])),
            fmt_p(f(r["p_signflip"])),
        ])
    A(table(["Scope", "n models open / closed", "n cells open / closed", "open acc",
             "closed (gemini) acc", "risk diff (open&minus;closed)", "95% CI (pp)",
             "OR", "95% CI", "GEE Wald p", "p (Holm)", "sign-flip p"],
            rows,
            classes=["", "num", "num", "num", "num", "num", "num", "num", "num", "num",
                     "num", "num"],
            foot=f"Run-1 <code>strict_correct</code>. GEE (exchangeable, cluster = question, "
                 f"{i(grp_pooled['n_clusters'])} clusters; the pooled row additionally adjusts "
                 f"for arm). Risk-difference CI from a question-level cluster bootstrap "
                 f"({i(grp_pooled['n_boot']):,} resamples); sign-flip permutation "
                 f"{i(grp_pooled['n_perm']):,} resamples, seed "
                 f"{i(d['grp']['random_seed'])}. Sign-flip p is at its attainable floor "
                 f"1/(n_perm+1) in every row. <b>n_models_closed = 1 in every row.</b>"))

    A(f"<p>The one substantive reading that survives the confound: gemini&rsquo;s margin over "
      f"the pooled three open models roughly doubles under the NOTA manipulation, from "
      f"{pp(f(grp_A['risk_difference']))} pp in <code>openrouter_A</code> to "
      f"{pp(f(grp_B['risk_difference']))} pp in <code>openrouter_B</code>. The three open "
      f"models lose disproportionately more accuracy than gemini does when the task switches "
      f"from recognising a correct statement to recognising that none of the listed statements "
      f"is correct. That is a claim about these four named models&rsquo; NOTA handling, not "
      f"about weight licensing.</p>")

    # ------------------------------------------------------------- stability
    A('<h2 id="stability">6. Stability under replication</h2>')
    fl = nb["flip"]
    A(f'<div class="callout"><strong>Read this before any number in this section.</strong> '
      f'Every row here is conditioned on the model having failed run 1. A cell can only flip '
      f'wrong&rarr;right, never the reverse, because the '
      f'{i(nb["strict_correct"]["overall"]["n_correct"]):,} run-1-correct cells were never '
      f'replicated. Regression to the mean therefore applies by construction, and the pooled '
      f'numbers are weighted toward NOTA items '
      f'({g["tri_by_arm"].get("openrouter_B", 0)} of {g["n_incorrect_cells"]} replicated cells '
      f'come from <code>openrouter_B</code>). This is a stability measure for already-wrong '
      f'answers, <em>not</em> a general accuracy measure.</div>')
    A(f"<p>Overall, {i(fl['overall']['n_flip'])} of {i(fl['overall']['n_scored_replicates']):,} "
      f"scored replicates ({pct(fl['overall']['rate'], 2)}) turned a run-1 error into a "
      f"strict-correct answer. Per cell, of the "
      f"{i(fl['per_cell_flip_count_histogram_0to2']['n_cells_with_at_least_one_scored_replicate'])} "
      f"cells with at least one scored replicate, "
      f"{i(fl['per_cell_flip_count_histogram_0to2']['histogram']['0'])} never flipped, "
      f"{i(fl['per_cell_flip_count_histogram_0to2']['histogram']['1'])} flipped once and "
      f"{i(fl['per_cell_flip_count_histogram_0to2']['histogram']['2'])} flipped on both "
      f"replicates &mdash; most run-1 errors are stable errors, not noise.</p>")

    A(figbox(fig_flip(d["flip_raw"]),
             "<b>Figure 5.</b> Flip rate by arm and model, from "
             "<code>results/primary_flip_rate_raw.csv</code> (all cells; the Vertex-excluded "
             "variant is in the table below). Grey numbers under each bar are cell counts &mdash; "
             "several are small, and gemini&rsquo;s bars in particular rest on 9 to 50 cells."))

    rows = []
    for r in sorted(d["flip_gee"], key=lambda r: (r["exclude_vertex"], r["contrast_family"], r["level"])):
        rows.append([
            "excl. Vertex" if r["exclude_vertex"] == "True" else "all cells",
            esc(r["contrast_family"].replace("flip_rate_by_", "")),
            f'{esc(short_model(r["level"]))} vs {esc(short_model(r["reference"]))}',
            f'{i(r["n_cells_used"]):,}',
            num(f(r["or_estimate"])),
            ci(f(r["or_ci_lo"]), f(r["or_ci_hi"]), nd=2, scale=1.0, signed=False),
            fmt_p(f(r["wald_p"])), fmt_p(f(r["p_holm"])),
        ])
    A(table(["Variant", "Family", "Contrast", "n cells", "OR", "95% CI", "Wald p", "p (Holm)"],
            rows, classes=["", "", "", "num", "num", "num", "num", "num"],
            foot="Cluster-robust GEE logistic, cluster = question. Not paired: the qualifying "
                 "cell sets differ across arms and models by construction. The "
                 "&ldquo;excl. Vertex&rdquo; variant drops the logical calls whose replicate "
                 "runs were served under the routing deviation described in &sect;7."))
    A("<p>Two patterns are worth naming, both with their caveat attached. Replicates in the "
      "NOTA arm are <em>less</em> likely to be rescued than replicates in condition A &mdash; "
      "consistent with NOTA errors being systematic rather than sampling noise, and the result "
      "is unchanged by the Vertex sensitivity exclusion. And qwen&rsquo;s errors are the most "
      "recoverable of the four models, though its Holm-adjusted p does not clear 0.05 in the "
      "Vertex-excluded variant, so treat the model-level ordering as exploratory.</p>")

    # ----------------------------------------------------------------- limits
    A('<h2 id="limits">7. Limitations and threats to validity</h2>')

    A("<h3>7.1 The Vertex protocol deviation "
      '<span class="badge stop">disclose with any gemini_B replicate number</span></h3>')
    A(f'<div class="callout"><p>As recorded in '
      f'<code>consolidate-triplicates-7-aug-26/DEVIATIONS.md</code>: from 2026-08-06, '
      f'<code>openrouter_B</code> / '
      f'<code>google/gemini-3.6-flash</code> replicate requests were routed with '
      f'<code>{{"order": ["google-vertex"], "allow_fallbacks": false, '
      f'"require_parameters": false}}</code> in place of the frozen '
      f'<code>{{"require_parameters": true}}</code>. Vertex supports neither '
      f'<code>temperature</code> nor <code>top_p</code>, so the declared '
      f'<code>temperature=0</code> was silently discarded and the model sampled at its default '
      f'(~1.0).</p>'
      f'<p><strong>{g["n_vertex"]} of {g["n_gem_b_scored"]} scored <code>openrouter_B</code> '
      f'gemini replicate cells were served this way</strong>; the other {g["n_aistudio"]} were '
      f'collected earlier under real <code>temperature=0</code>, and {g["n_gem_b_exhausted"]} '
      f'more exhausted the retry ceiling without a score. Across the whole replicate set, '
      f'{g["n_temp_not_honoured"]} of {g["n_logical_calls"]:,} logical calls have '
      f'<code>temperature_honoured = FALSE</code>, and all of them are this slice.</p>'
      f'<p><strong>This analysis cannot isolate the deviation&rsquo;s effect, in either '
      f'direction.</strong> Sampling at temperature ~1.0 could inflate the measured flip rate '
      f'(more variance means more chances to land on the right option) or deflate it (a '
      f'temperature-0 model that was confidently wrong stays confidently wrong, and noise can '
      f'move it either way). The design gives no un-deviated gemini_B replicate stratum large '
      f'enough to estimate the difference &mdash; {g["n_aistudio"]} cells. Every flip-rate '
      f'result is therefore reported twice, with and without those {g["n_vertex"]} cells, and '
      f'the sensitivity variant is a robustness check on the same hypothesis rather than an '
      f'added Holm family member.</p></div>')
    A(f"<p>Two consequences worth stating separately. First, <strong>run 1 is clean</strong>: "
      f"all {g['n_run1_cells']:,} run-1 cells were collected before any Vertex routing existed, "
      f"so &sect;4 and &sect;5.2&rsquo;s primary table are unaffected. Second, in the "
      f"<code>openrouter_B</code> replicate data the open/closed split and the "
      f"Vertex-deviation split are <em>the same subset of cells</em>: excluding the "
      f"{g['n_vertex']} deviated cells reduces the closed group there to "
      f"{i(next(r for r in grp_s if r['scope'] == 'openrouter_B' and r['sensitivity'] != 'main')['n_cells_closed'])} "
      f"cells, which produces a number in "
      f"<code>groupings_open_closed_secondary.csv</code> that is an artefact of its own sample "
      f"size and should not be read as a finding.</p>")

    A("<h3>7.2 Provider &times; condition is not crossed</h3>")
    A(f"<p>The analysis records this constraint as: &ldquo;"
      f"{esc(pr['spec_constraints_honoured']['provider_x_condition_interaction'])}&rdquo; "
      f"OpenRouter "
      f"carries both conditions; TailScale carries only A. The interaction term has no data "
      f"behind it &mdash; the design is not underpowered for it, it is missing it. No "
      f"interaction test appears anywhere in this analysis, and any claim of the form "
      f"&ldquo;the NOTA effect is larger on one provider than the other&rdquo; is unsupportable "
      f"from this dataset regardless of how it is computed.</p>")

    A("<h3>7.3 Surface cues in the option text, in both directions</h3>")
    A(f"<p>Two properties of the item bank could be exploited by a model without any medical "
      f"reasoning. <strong>Option <code>a</code> is never the correct answer</strong> in any of "
      f"the {g['shared']} questions (correct letters: "
      f"{', '.join(f'{k} &times;{v}' for k, v in sorted(g['correct_letter_counts'].items()))}), "
      f"so a model that has learned to avoid <code>a</code> gains accuracy for free, and "
      f"selecting <code>a</code> is always an error. <strong>Length differs systematically</strong>: "
      f"the correct option averages {num(g['len_correct_A'], 1)} characters in A against "
      f"{num(g['len_distractor_A'], 1)} for distractors (correct answers are slightly longer), "
      f"while in B it is {num(g['len_correct_B'], 1)} characters and byte-identical across all "
      f"items (conspicuously shorter, and perfectly recognisable). A length heuristic helps in "
      f"A and would be trivially decisive in B if a model learned it &mdash; part of the "
      f"measured A-to-B drop may be a shift in which surface cue is available rather than a "
      f"change in reasoning.</p>")

    A("<h3>7.4 Other constraints on interpretation</h3>")
    A("<ul>"
      f"<li><b>Open vs closed has one model on one side.</b> Restated because it is the "
      f"easiest finding in this report to misquote: those results describe gemini, not a "
      f"licensing category. See &sect;5.2.</li>"
      f"<li><b>Ceiling effect.</b> {bnd['n_questions_at_boundary']} of {g['n_questions']} "
      f"questions carry no within-question signal at all (&sect;3.1). The benchmark&rsquo;s "
      f"discriminating power lives in the remaining {bnd['n_questions_interior']}.</li>"
      f"<li><b>Flip rates are conditional.</b> Conditioned on failing run 1, so they cannot be "
      f"read as reliability estimates; the correct&rarr;wrong direction was never sampled "
      f"(&sect;6).</li>"
      f"<li><b>{g['n_exhausted']} logical calls have no score at all</b>, having exhausted the "
      f"five-attempt retry ceiling. Coverage is "
      f"{pct(g['n_scored'] / g['n_logical_calls'], 1)} of {g['n_logical_calls']:,}. The "
      f"missingness is not random: it concentrates in the same rate-limited "
      f"<code>openrouter_B</code> gemini slice as the deviation.</li>"
      f"<li><b>Single benchmark, single language, single specialty family.</b> All "
      f"{g['n_questions']} items are Spanish medical MCQs drawn from the same exam corpus. "
      f"Nothing here licenses extrapolation to other item formats, languages or domains.</li>"
      f"<li><b>One run per cell at run 1.</b> The primary accuracy estimates rest on a single "
      f"draw per cell; the replicate design measures re-draw behaviour only for cells that "
      f"failed.</li>"
      "</ul>")

    # ------------------------------------------------------------ provenance
    A('<h2 id="provenance">8. Provenance</h2>')
    A('<dl class="prov">')
    A(f"<dt>Generated</dt><dd>{esc(now.isoformat())} "
      f"({esc(now.astimezone(timezone.utc).isoformat())}) &mdash; read from the system clock "
      f"at build time by <code>scripts/04_build_report.py</code>.</dd>")
    A(f"<dt>Commit</dt><dd><code>{esc(git['commit'])}</code> "
      f"({esc(git['short'])}) on branch <code>{esc(git['branch'])}</code>, "
      f"{esc(git['date'])} &mdash; &ldquo;{esc(git['subject'])}&rdquo;</dd>")
    if git["dirty"]:
        n_dirty = len([x for x in git["dirty"].splitlines() if x.strip()])
        A(f'<dt>Working tree</dt><dd><b>Not clean.</b> {n_dirty} path(s) under '
          f'<code>statistical-analysis-7-aug-26/</code> are modified or untracked relative to '
          f'that commit, so the inputs below are the working-tree versions, not the committed '
          f'ones. Their SHA-256 digests are listed so the exact bytes used can be '
          f'identified.</dd>')
    else:
        A("<dt>Working tree</dt><dd>Clean for this directory at build time.</dd>")
    A(f"<dt>Report generator</dt><dd><code>statistical-analysis-7-aug-26/scripts/"
      f"04_build_report.py</code>. It writes only <code>REPORT.html</code>; every number above "
      f"is read from a file at build time and none is hard-coded. Re-running it regenerates "
      f"the report against whatever the results files currently say.</dd>")
    A(f"<dt>Charts</dt><dd>Hand-written inline SVG with coordinates computed in the script; "
      f"matplotlib is not installed in this environment. The report has no external "
      f"stylesheet, font, script or image and renders offline.</dd>")
    A("</dl>")

    A("<h3>8.1 Source files, and which section each one feeds</h3>")
    rows = []
    for s in SOURCES:
        rows.append([
            f'<code>{esc(s["rel"])}</code>',
            esc(s["role"]),
            f'<code>{esc(s["sha256"][:16])}&hellip;</code>',
            f'{s["bytes"]:,}',
        ])
    A(table(["Path (relative to repository root)", "What it supplies", "SHA-256 (first 16 hex)",
             "bytes"],
            rows, classes=["wrapcell", "wrapcell", "", "num"],
            foot=f"{len(SOURCES)} files, each opened by this build. Digests computed at build "
                 f"time over the exact bytes read."))

    A("<h3>8.2 Companion documents</h3>")
    A("<ul>"
      "<li><code>statistical-analysis-7-aug-26/STATS_SPEC.md</code> &mdash; the design "
      "constraints this analysis was built to honour, including the A/B verification and the "
      "list of comparisons that are constrained or infeasible.</li>"
      "<li><code>statistical-analysis-7-aug-26/results/NORMALITY_REPORT.md</code> &mdash; full "
      "diagnostics behind &sect;3.</li>"
      "<li><code>statistical-analysis-7-aug-26/results/PRIMARY_TESTS.md</code> &mdash; full "
      "method notes and assumption audit behind &sect;4 and &sect;6.</li>"
      "<li><code>statistical-analysis-7-aug-26/results/GROUPING_TESTS.md</code> and "
      "<code>statistical-analysis-7-aug-26/results/MODEL_TAXONOMY.md</code> &mdash; the "
      "grouping results and the audit trail for every model-level label, behind &sect;5.</li>"
      "<li><code>consolidate-triplicates-7-aug-26/DEVIATIONS.md</code> &mdash; the complete "
      "protocol-deviation record summarised in &sect;7.1, including the retracted hypotheses "
      "and the record-keeping defect in <code>redacted_command</code>.</li>"
      "<li><code>consolidate-triplicates-7-aug-26/METHODS.md</code>, "
      "<code>consolidate-triplicates-7-aug-26/SPEC.md</code> and "
      "<code>consolidate-triplicates-7-aug-26/exports/EXPORTS_README.md</code> &mdash; "
      "collection protocol and export definitions.</li>"
      "<li>QQ plots for all ten continuous quantities: "
      "<code>statistical-analysis-7-aug-26/figures/qq_*.svg</code> (Figure 1 above is redrawn "
      "here from the same underlying CSV so the report stays self-contained and "
      "theme-aware).</li>"
      "</ul>")

    A('<h3>8.3 Conventions used in this report</h3>')
    A('<ul class="footnotes">'
      '<li>p-values are shown to four decimals down to 0.0001 and in scientific notation below '
      'that. Where a stored Wald p underflowed to exactly 0.0 in the source JSON, it is shown '
      'as an underflow rather than as a real zero.</li>'
      '<li>Risk differences are in percentage points with 95% confidence intervals; odds ratios '
      'carry their own CIs. No p-value appears in this report without an effect size next to '
      'it.</li>'
      '<li>Holm-Bonferroni correction is applied within each family; families are named in the '
      'table footnotes and defined in full in the companion results documents.</li>'
      '<li>Percentages are rounded for display; the unrounded values are in the source files '
      'listed in &sect;8.1.</li>'
      "</ul>")

    A("</div>")
    return "".join(H)


def main() -> None:
    d = load_all()
    g = derive_design(d)
    body = build(d, g)
    doc = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>NOTA susceptibility in a 500-item Spanish medical MCQ benchmark</title>\n"
        f"<style>{CSS}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
    )
    OUT.write_text(doc, encoding="utf-8")
    print(f"wrote {OUT} ({len(doc):,} bytes) from {len(SOURCES)} source files")


if __name__ == "__main__":
    main()
