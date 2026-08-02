"""Merged loader: paired_clean.json cells + the reasoning/answer token split.

Adds per cell:
  A_reason, B_reason      reasoning (thinking) tokens
  A_answer, B_answer      completion_tokens - reasoning_tokens  (the emitted
                          JSON answer, which echoes the chosen option's text)
  A_seltext_chars, B_seltext_chars  characters of the echoed option text
"""
import json
from mech_lib_effort import load, MODELS, SHORT  # noqa: F401

EXP = {"A": "expA_or_310726", "B": "expB_or_310726"}
RJ = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
      "experiment-31-07-26/analysis/mech_db_reasoning.json")


def load_merged():
    rows = load()
    db = {}
    for c in json.load(open(RJ)):
        db[tuple(c["key"])] = c
    out = []
    for r in rows:
        ok = True
        r = dict(r)
        for cond in "AB":
            c = db.get((EXP[cond], r["model"], r["question_id"]))
            if c is None or c["reasoning_tokens"] is None:
                ok = False
                break
            r[cond + "_reason"] = c["reasoning_tokens"]
            r[cond + "_answer"] = c["completion_tokens"] - c["reasoning_tokens"]
            r[cond + "_seltext_chars"] = c["sel_text_chars"]
            r[cond + "_created"] = c["created_at"]
            # provider-independent fallbacks measured off the raw response body
            r[cond + "_rchars"] = c["reasoning_chars"]
            r[cond + "_cchars"] = c["content_chars"]
        if ok:
            out.append(r)
    return out


if __name__ == "__main__":
    rs = load_merged()
    print("merged cells:", len(rs))
    neg = sum(1 for r in rs for c in "AB" if r[c + "_answer"] < 0)
    print("negative answer-token cells:", neg)
    zero_sel = sum(1 for r in rs for c in "AB" if r[c + "_seltext_chars"] == 0)
    print("cells with unparsed echoed option text:", zero_sel)
