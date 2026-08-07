"""Validate every experiment-5 prompt template (reusable QA gate).

OpenRouter forms (variants/*_user_template.txt): must render under Python str.format using ONLY the six
allowed placeholders (a stray single brace or unknown placeholder is a hard fail), and must end with the
canonical question block.
GIFT forms (variants/gift13/*_prompt13_es.txt): {chunks} and {question} must each appear exactly once;
the injection label must be correctly accented ("Contexto médico recuperado").

Exit non-zero if any check fails.
"""
from __future__ import annotations
import sys
from pathlib import Path
from string import Formatter

HERE = Path(__file__).resolve().parent
VARIANTS = HERE.parent / "variants"
GIFT = VARIANTS / "gift13"
ALLOWED = {"question_id", "question_text", "option_a", "option_b", "option_c", "option_d"}
DUMMY = {k: "x" for k in ALLOWED}
QBLOCK_TAIL = "Opciones:"  # OR forms must contain the question block

def check_or(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errs: list[str] = []
    try:
        for _, field, _, _ in Formatter().parse(text):
            if field:
                base = field.split(".", 1)[0].split("[", 1)[0]
                if base not in ALLOWED:
                    errs.append(f"disallowed placeholder {{{base}}}")
        text.format(**DUMMY)
    except Exception as e:
        errs.append(f"render error {type(e).__name__}: {e}")
    for ph in ("{question_id}", "{question_text}", "{option_a}", "{option_b}", "{option_c}", "{option_d}"):
        if ph not in text:
            errs.append(f"missing placeholder {ph}")
    if QBLOCK_TAIL not in text:
        errs.append("missing question block ('Opciones:')")
    return errs

def check_gift(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errs: list[str] = []
    for tok, n in (("{chunks}", text.count("{chunks}")), ("{question}", text.count("{question}"))):
        if n != 1:
            errs.append(f"{tok} appears {n}x (must be exactly 1)")
    if "Contexto medico recuperado" in text:
        errs.append("unaccented label 'Contexto medico recuperado' (should be 'médico')")
    return errs

def main() -> int:
    ors = sorted(VARIANTS.glob("*_user_template.txt"))
    gifts = sorted(GIFT.glob("*_prompt13_es.txt"))
    fails = 0
    print(f"OpenRouter forms ({len(ors)}):")
    for p in ors:
        e = check_or(p); fails += bool(e)
        print(f"  {'OK  ' if not e else 'FAIL'} {p.name}" + ("" if not e else "  -> " + "; ".join(e)))
    print(f"GIFT-13 forms ({len(gifts)}):")
    for p in gifts:
        e = check_gift(p); fails += bool(e)
        print(f"  {'OK  ' if not e else 'FAIL'} {p.name}" + ("" if not e else "  -> " + "; ".join(e)))
    print(f"\n{'ALL TEMPLATES VALID' if not fails else str(fails) + ' TEMPLATE(S) FAILED'}")
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main())
