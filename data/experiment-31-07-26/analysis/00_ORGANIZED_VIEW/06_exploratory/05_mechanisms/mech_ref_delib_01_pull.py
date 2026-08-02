"""REFUTATION pull: reasoning tokens per scored cell, condition A vs B (OpenRouter arm).

Independent of mech_00b/mech_merge. Reaches the SCORED attempt only, via
scores -> parsed_answers.provider_attempt_id -> provider_attempts, exactly as
build_analysis_data.py does, so the cell set matches paired_clean.json.

Writes mech_ref_delib_cells.json
"""
import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE.parent / "experiment.sqlite"

SQL = """
SELECT q.question_id AS qid, lc.model AS model,
       a.id AS attempt_id, a.completion_tokens AS ctok, a.prompt_tokens AS ptok,
       a.finish_reason AS finish, a.latency_ms AS lat,
       a.response_json AS rj, a.response_body AS body,
       s.strict_correct AS correct
FROM scores s
JOIN logical_calls lc    ON lc.id = s.logical_call_id
JOIN questions q         ON q.id  = lc.question_id
JOIN parsed_answers p    ON p.logical_call_id = lc.id
JOIN provider_attempts a ON a.id  = p.provider_attempt_id
JOIN experiments e       ON e.id  = lc.experiment_id
WHERE e.name = ?
"""


def pull(conn, exp):
    out = {}
    for r in conn.execute(SQL, (exp,)):
        if r["correct"] is None:
            continue
        rj = json.loads(r["rj"]) if r["rj"] else {}
        body = {}
        try:
            body = json.loads(r["body"]) or {}
        except Exception:
            pass
        usage = (rj or {}).get("usage") or {}
        det = usage.get("completion_tokens_details") or {}
        ch = ((rj or {}).get("choices") or [{}])[0]
        msg = ch.get("message") or {}
        content = msg.get("content") or ""
        reasoning_txt = msg.get("reasoning") or ""
        out[(r["qid"], r["model"])] = {
            "attempt_id": r["attempt_id"],
            "ctok": r["ctok"],
            "ptok": r["ptok"],
            "finish": r["finish"],
            "lat": r["lat"],
            "correct": int(r["correct"]),
            "reason_tok": det.get("reasoning_tokens"),
            "has_details": bool(det),
            "content_chars": len(content),
            "reasoning_chars": len(reasoning_txt),
            "backend": body.get("provider") or rj.get("provider"),
            "native_finish": ch.get("native_finish_reason"),
        }
    return out


def main():
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    A = pull(conn, "expA_or_310726")
    B = pull(conn, "expB_or_310726")

    paired = json.loads((HERE / "paired_clean.json").read_text(encoding="utf-8"))
    idx = {(r["question_id"], r["model"]): r for r in paired}

    rows = []
    miss = 0
    for k in sorted(set(A) & set(B), key=lambda k: (int(k[0][1:]), k[1])):
        base = idx.get(k)
        if base is None:
            miss += 1
            continue
        a, b = A[k], B[k]
        rec = {
            "question_id": k[0], "model": k[1],
            "cluster": base["cluster"], "correct_letter": base["correct_letter"],
            "negated_stem": base["negated_stem"], "has_context": base["has_context"],
            "qlen": base["qlen"],
            "analysis_include": base["analysis_include"],
            "A_correct": base["A_correct"], "B_correct": base["B_correct"],
            "A_selected": base["A_selected"], "B_selected": base["B_selected"],
        }
        for tag, d in (("A", a), ("B", b)):
            for f in ("ctok", "ptok", "finish", "lat", "reason_tok", "has_details",
                      "content_chars", "reasoning_chars", "backend", "native_finish"):
                rec[f"{tag}_{f}"] = d[f]
        # sanity: token columns must agree with paired_clean
        assert rec["A_ctok"] == base["A_tokens"], (k, rec["A_ctok"], base["A_tokens"])
        assert rec["B_ctok"] == base["B_tokens"], (k, rec["B_ctok"], base["B_tokens"])
        assert rec["A_backend"] == base["A_backend"]
        assert rec["B_backend"] == base["B_backend"]
        rows.append(rec)

    (HERE / "mech_ref_delib_cells.json").write_text(json.dumps(rows), encoding="utf-8")
    inc = [r for r in rows if r["analysis_include"]]
    print(f"paired cells pulled : {len(rows)}   (not in paired_clean: {miss})")
    print(f"analysis_include    : {len(inc)}  items={len({r['question_id'] for r in inc})}"
          f"  clusters={len({r['cluster'] for r in inc})}"
          f"  models={len({r['model'] for r in inc})}")
    for m in sorted({r["model"] for r in inc}):
        s = [r for r in inc if r["model"] == m]
        na = sum(1 for r in s if r["A_reason_tok"] is None)
        nb = sum(1 for r in s if r["B_reason_tok"] is None)
        print(f"  {m:26} n={len(s):4}  reasoning_tokens missing A={na} B={nb}")


if __name__ == "__main__":
    main()
