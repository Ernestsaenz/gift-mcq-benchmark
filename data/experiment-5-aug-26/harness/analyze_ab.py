"""Combined Condition-A/B analysis — separates genuine NOTA-robustness from over-abstention.

Reads the Condition-B run (results/*.jsonl) and the Condition-A regression (results/condition-A/*.jsonl).
For each variant reports B accuracy, A accuracy, ΔB (vs B baseline) and ΔA (vs A baseline).

Interpretation on these 10 items (correct answer = the sentinel in B, a real option in A):
  - ΔB > 0 and ΔA ≈ 0  -> GENUINE: recognizes answer-absence without hurting normal items.
  - ΔB > 0 and ΔA << 0 -> OVER-ABSTENTION ARTIFACT: gains on B by over-picking the sentinel, costs A.
  - ΔB ≈ 0             -> no effect.
Writes results/condition-AB-summary.csv and prints a ranked verdict table.
"""
from __future__ import annotations
import glob, json, csv
from collections import defaultdict
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent

def load(pattern: str) -> dict:
    acc = defaultdict(lambda: [0, 0])   # variant -> [correct, total]
    accm = defaultdict(lambda: [0, 0])  # (variant, model) -> [correct, total]
    for f in glob.glob(pattern):
        for l in open(f, encoding="utf-8"):
            if not l.strip():
                continue
            r = json.loads(l)
            v = r["variant"]; ok = 1 if r.get("strict_correct") else 0
            acc[v][0] += ok; acc[v][1] += 1
            accm[(v, r["model_alias"])][0] += ok; accm[(v, r["model_alias"])][1] += 1
    return acc, accm

def pct(cell): return 100.0 * cell[0] / cell[1] if cell[1] else float("nan")

def main() -> None:
    B, Bm = load(str(EXP / "results" / "*.jsonl"))
    A, Am = load(str(EXP / "results" / "condition-A" / "*.jsonl"))
    if not A:
        raise SystemExit("no Condition-A results yet at results/condition-A/*.jsonl")
    baseB, baseA = pct(B["baseline"]), pct(A["baseline"])

    # variant order is auto-discovered from the data (baseline first, then sorted)
    order = (["baseline"] if "baseline" in (set(B) | set(A)) else []) + \
            sorted(v for v in (set(B) | set(A)) if v != "baseline")
    rows = []
    for v in order:
        accB, accA = pct(B[v]), pct(A[v])
        dB, dA = accB - baseB, accA - baseA
        if v == "baseline":
            verdict = "reference"
        elif dB >= 10 and dA >= -5:
            verdict = "GENUINE (B↑, A held)"
        elif dB >= 10 and dA <= -10:
            verdict = "OVER-ABSTENTION (B↑ but A↓)"
        elif dB >= 10:
            verdict = "likely genuine (mild A dip)"
        elif dB <= 5 and dA <= -10:
            verdict = "HARMFUL (A↓, no B gain)"
        else:
            verdict = "no effect"
        rows.append((v, accB, dB, accA, dA, accB + accA - baseB - baseA, verdict))

    with (EXP / "results" / "condition-AB-summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["variant", "B_acc%", "dB_pp", "A_acc%", "dA_pp", "net_pp(dB+dA)", "verdict"])
        for r in rows:
            w.writerow([r[0], f"{r[1]:.0f}", f"{r[2]:+.0f}", f"{r[3]:.0f}", f"{r[4]:+.0f}", f"{r[5]:+.0f}", r[6]])

    print(f"Baseline: B={baseB:.0f}%  A={baseA:.0f}%   (n=20 per cell)\n")
    hdr = f"{'variant':9s} {'B%':>4s} {'ΔB':>5s} {'A%':>4s} {'ΔA':>5s} {'net':>5s}  verdict"
    print(hdr); print("-" * len(hdr))
    for v, accB, dB, accA, dA, net, verdict in sorted(rows, key=lambda r: (-r[2], r[4])):
        print(f"{v:9s} {accB:>3.0f}% {dB:>+4.0f} {accA:>3.0f}% {dA:>+4.0f} {net:>+4.0f}  {verdict}")
    print("\nwrote results/condition-AB-summary.csv")

if __name__ == "__main__":
    main()
