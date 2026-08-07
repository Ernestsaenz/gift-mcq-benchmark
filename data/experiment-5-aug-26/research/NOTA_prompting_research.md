# Prompting techniques to improve LLM accuracy under the NOTA (none-of-the-above) transform

Synthesis of the 5-cluster web research (see `research-raw.json` for the full structured findings and
the independent QA note in `qa1-verdict.json`). This grounds the 10 variants in `../variants/`.

## The core finding

Condition B replaces the correct option with *"Ninguna de las respuestas anteriores es correcta."* so
the true answer is **absent**. Two 2025 papers isolate exactly this failure:

- **Tam et al. 2025, "None of the Above, Less of the Right"** (ACL Findings) and **Elhady et al. 2025,
  "WiCkeD"** show LLMs lose large accuracy (reported ranges ~12–50 pp) specifically because they **lack
  the meta-cognitive habit of systematically rejecting *all* options when none is correct** — they pick
  the *least-incorrect* surviving distractor.
- **"LLMs May Perform MCQA by Selecting the Least Incorrect Option"** (COLING 2025) names the same
  mechanism: models optimize "least wrong," not "actually right."

Crucially, **both papers report that generic chain-of-thought does *not* close the gap by itself.** The
live `mcq_es_v4` prompt gives the sentinel **no policy at all**, which is precisely the diagnosed
failure condition. So the highest-leverage change is an **explicit, rule-governed policy for the
sentinel**, not merely "think step by step."

## Mechanisms that address it → variants

| Mechanism (research) | Key sources | Variant(s) |
|---|---|---|
| **Explicit NOTA decision rule** — declare the sentinel a valid, non-trick option; pick it only when *none* of a–d is *absolutely* correct (not "least wrong") | Tam 2025; WiCkeD 2025; Least-Incorrect (COLING 2025) | **v02**, folded into v10 |
| **Recall-first / step-back derivation** — derive the guideline answer *before* seeing options, then match; if no match → NOTA (counters anchoring at its source) | Step-Back (Zheng 2023); Generated Knowledge (Liu 2022); Plan-and-Solve (Wang 2023) | **v01**, **v06**, v10 |
| **Per-option verification framed as *support*, not refutation** | POE (Ma 2023); CoVe (Dhuliawala 2024); **Balepur 2024 "It's Not Easy Being Wrong"** (refutation-style POE *underperforms* direct answering) | **v05**, v10 |
| **General clinical CoT** (deliberate reasoning before commit) — a control to measure CoT-alone | Kojima 2022; Liévin 2024 (medical) | **v04** |
| **Self-check / verify-revise in one pass** (draft → self-critique → finalize) | Self-Refine (Madaan 2023); Self-Verification (Weng 2022); CoVe | **v07** |
| **Calibrated abstention routed to the sentinel** — self-rated confidence, but tied to *answer-absence*, not mere uncertainty | Abstention survey (2024); "Do LLMs Know When to NOT Answer" (2024); abstention-artifact (2025) | **v08** (see caution) |
| **Few-shot NOTA exemplars** (one sentinel-correct, one not — avoid NOTA bias) | Medprompt (Nori 2023) | **v03** |
| **RAG-grounded per-option verification** — use retrieved `{chunks}` to establish the guideline fact, verify each option, absent → NOTA | Self-RAG (Asai 2023); Chain-of-Note (Yu 2024); Context-faithful (Zhou 2023); Corrective-RAG (Yan 2024); RAGAS faithfulness | **v09**, v10 (GIFT forms) |

## Key cautions (baked into the variants and the QA gate)

1. **CoT alone is not the fix.** Both NOTA papers show it; **"Why CoT Fails in Clinical Text"** (2025)
   and selective-CoT work argue blanket CoT can even hurt on knowledge items. → We include v04 as a
   *control*, and every targeted variant adds a specific NOTA/anchoring mechanism, not just reasoning.
2. **Elimination by refutation backfires.** Balepur 2024 shows reasoning about *why options are wrong*
   underperforms. → v05 is framed as **support/verification** ("¿respalda la evidencia esta opción?"),
   not "argue why it's false."
3. **Over-abstention risk.** Aggressive sentinel rules or "when unsure → none" **over-pick NOTA**, which
   would *inflate* Condition-B while destroying Condition-A. The abstention-artifact paper (2025) warns
   abstention can be a pure prompt artifact. → v02/v10 use **symmetric** rules ("absolute, not
   relative"; "do not avoid it when genuinely correct"); v08 was **corrected in QA** to tie the sentinel
   to *answer-absence*, not low confidence, with an explicit Condition-A guard. **This is why a
   Condition-A regression check matters** (see README caveat) — a B-only gain can be an over-abstention
   artifact.
4. **Self-consistency / choice-shuffle ensembling** (multi-sample majority vote) is powerful but needs
   temperature > 0 and multiple calls — **out of scope** for this single-call, temp-0 harness. Noted for
   a future multi-sample study.

## The RAG endgame

The ultimate target is GIFT/Tailscale Condition-B, where retrieved `{chunks}` are available. The
grounded-verification line (Self-RAG, Chain-of-Note, Context-faithful, Corrective-RAG) is designed so
retrieved evidence **establishes the guideline-correct fact independently of the options** — the ideal
signal for detecting answer-absence. v09 and the GIFT forms of v05/v10 operationalize this. The
OpenRouter proxy (no chunks) therefore **under-estimates** these variants; their `{chunks}` clause is
inert until retrieval is wired in.

## Citations (34; verify the post-cutoff ones before any public use)

**Verified / well-known (pre-2025):** Kojima 2022 (2205.11916) · Generated Knowledge 2022 (2110.08387)
· Self-Consistency 2022 · Self-Verification (Weng) 2022 (2212.09561) · Plan-and-Solve 2023 (2305.04091)
· Step-Back 2023 (2310.06117) · Self-Refine 2023 (2303.17651) · Context-faithful 2023 (2303.11315) ·
POE 2023 (2310.15575) · Self-RAG 2023 (2310.11511) · Medprompt 2023 (2311.16452) · Chain-of-Note 2024
(2311.09210) · CoVe 2024 (2309.11495) · Corrective-RAG 2024 (2401.15884) · Balepur "It's Not Easy Being
Wrong" (ACL Findings 2024) · Liévin medical-QA 2024 (2207.08143) · Abstention survey 2024 (2407.18418) ·
"Do LLMs Know When to NOT Answer" 2024 (2407.16221) · self-reflection medical RAG (PMC11211826).

**On-topic 2025, plausible but at/after cutoff — CHECK:** Tam "None of the Above" (ACL Findings 2025 /
2503.01550) · WiCkeD (2502.18316) · Least-Incorrect (COLING 2025 / 2402.01349) · "None of the Others"
(2502.12896) · abstention-artifact (2507.16199) · "Reasoning Models are Test Exploiters" (2507.15337) ·
"Why CoT Fails in Clinical Text" (2509.21933) · MedReflect (2510.03687) · Calibrating Certainty
(2410.04315).

**⚠ Suspect / do NOT cite without verifying (QA-flagged):** "To Reason or Not to: Selective CoT in
Medical QA" (2602.20130, dated 2026-02) · **"Quantifying and Mitigating Premature Closure in Frontier
LLMs" (2605.15000)** — the QA reviewer judged this identifier likely fabricated.

Non-paper references: Anthropic "Reduce hallucinations" docs; RAGAS faithfulness metric docs.
