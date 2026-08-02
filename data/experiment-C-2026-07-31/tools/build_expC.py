"""Experiment C — deterministic construction of the fabricated-entity item set.

Reads balanced-flat-A.xlsx read-only and emits canonical.json: for every one of the
474 rows, the eligibility verdict and the guard that rejected it; and for every
eligible row, the CTRL / BM / AN variants of question_text.

NO LANGUAGE MODEL IS INVOLVED IN GENERATION. Every modified string is produced by
    new = pre + SENTENCE + sep + tail
where (pre, sep, tail) come from a regex seam and SENTENCE is a literal constant
from the table below. Byte-level assertions prove nothing else moved.

Guard lettering follows the reviewed specification. Two funnels are emitted:
  STRICT   guards A-I then J-N            -> paired set of 37
  RELAXED  guards A-I then K-N (J dropped) -> paired set of 58
J removes decision-type stems ("¿cuál es el siguiente paso?"). It protects the
answer key at the cost of removing precisely the items where a model is most
likely to *use* the fabricated finding, so it is reported both ways rather than
silently chosen.
"""
from __future__ import annotations

import collections
import json
import re
import unicodedata
from pathlib import Path

import openpyxl

SRC = Path("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data"
           "/experiment-31-07-26/balanced-flat-A.xlsx")
OUT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------
# The twenty fabricated-entity sentences. Literal constants; never generated.
# `root` is the morpheme used to test lexical camouflage: if the row's own text
# already contains it, the fabricated term can be assimilated as an echo of the
# vignette's vocabulary rather than noticed as novel, so that pairing is refused.
# --------------------------------------------------------------------------
BIOMARKERS = {
    "BM01": ("hepatovirelina-3", "En la analítica destaca una elevación de la hepatovirelina-3 sérica.", "hepat"),
    "BM02": ("colangiomirina-8", "La colangiomirina-8 plasmática se encuentra por encima del intervalo de referencia.", "colangi"),
    "BM03": ("enterovexina-R2", "La determinación de enterovexina-R2 fecal resulta positiva.", "entero"),
    "BM04": ("pancreocerina-K4", "La pancreocerina-K4 sérica está elevada.", "pancre"),
    "BM05": ("gastrofollina-P6", "La gastrofollina-P6 plasmática presenta un valor anormal.", "gastr"),
    "BM06": ("mucorynex-Z9", "La determinación de mucorynex-Z9 en saliva resulta positiva.", "muco"),
    "BM07": ("fibroquelina-X3", "La fibroquelina-X3 sérica se encuentra aumentada.", "fibro"),
    "BM08": ("portalectina-Q5", "La portalectina-Q5 plasmática supera el límite superior de normalidad.", "portal"),
    "BM09": ("ileovarina-T5", "La determinación de ileovarina-T5 fecal se encuentra elevada.", "ileo"),
    "BM10": ("colonorelina-M7", "La colonorelina-M7 sérica resulta positiva.", "colon"),
}
ANATOMY = {
    "AN01": ("glándula maroviana", "La ecografía describe un aumento de tamaño de la glándula maroviana.", "marovian"),
    "AN02": ("cuerpo valdrénico", "La tomografía computarizada muestra edema del cuerpo valdrénico.", "valdren"),
    "AN03": ("órgano neraliano", "La resonancia magnética identifica inflamación del órgano neraliano.", "neralian"),
    "AN04": ("saco orfalónico", "La exploración revela dolor a la palpación del saco orfalónico.", "saco"),
    "AN05": ("glándula cavorelliana", "La ecografía objetiva dilatación de la glándula cavorelliana.", "cavorellian"),
    "AN06": ("cuerpo treliano", "La tomografía computarizada muestra engrosamiento del cuerpo treliano.", "trelian"),
    "AN07": ("órgano pelvórico", "La resonancia magnética evidencia compresión del órgano pelvórico.", "pelvoric"),
    "AN08": ("glándula sereviana", "La ecografía describe cambios inflamatorios en la glándula sereviana.", "serevian"),
    "AN09": ("cuerpo dorválico", "La tomografía computarizada identifica una lesión focal en el cuerpo dorválico.", "dorvalic"),
    "AN10": ("órgano liradónico", "La exploración muestra sensibilidad localizada sobre el órgano liradónico.", "organo"),
}
# Rotated within arm so the entity is never aliased with cluster or region.
# Only serum/plasma biomarkers survive the specimen gate; only the two
# examination-based anatomy sentences survive the modality gate.
BM_ROTATION = ["BM07", "BM02", "BM04", "BM08"]
AN_ROTATION = ["AN04", "AN10"]

# --------------------------------------------------------------------------
# Normalisation and seam
# --------------------------------------------------------------------------
def nf(s: str) -> str:
    """NFD -> strip combining marks -> collapse whitespace -> lowercase.

    The whitespace collapse is load-bearing: the source PDFs wrap lines mid-phrase,
    so `Las únicas\nalteraciones analíticas` must normalise to one space or the
    lab-normality gate silently under-fires.
    """
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s).lower()
    return re.sub(r"normal\s*:", "REFRANGE:", s)


BOUND = re.compile(r"(?:(?<=[.!?])\s+|\n+)")
STEM = re.compile(
    r"^\W*(?:[Ss]e[ñn]ale|[Ss]e[ñn]ala|[Ii]ndique|[Ii]ndica|[Dd]escriba|[Dd]escribe|[Mm]arque"
    r"|[Ee]lija|[Ss]eleccione|[Ee]scoja|[Dd]iga|[Cc]onteste|[Rr]esponda|[Ii]dentifique"
    r"|[CcQq]u[aá]l(?:es)?|[Qq]u[eé]|[Cc][oó]mo|[Cc]u[aá]ndo|[Dd][oó]nde|[Cc]u[aá]nt[oa]s?"
    r"|[Qq]ui[eé]n(?:es)?)\b")
TAILEND = re.compile(r"(?i)(excepto|falsa|falso|correcta|incorrecta|verdadera|cierta"
                     r"|siguientes|ser[ií]a|sospecha diagn|es:)")
MEAS = re.compile(r"(?i)\d[\d.,]*\s*(mg|g/dl|gr|dl|ml|ui|u/l|cm|mm|%|mmhg|lpm|x\s*10|/mm)")
# Accented forms only. Writing `qu[eé]` here matches the relative pronoun `que`
# and wrongly kills 38 rows.
PREVQ = re.compile(r"[¿?]|\b(qué|cuál|cuáles|cuándo|cómo|dónde|cuánto|cuántos|cuánta"
                   r"|cuántas|quién|quiénes)\b", re.I)
PREVSTEM = re.compile(r"^\W*(?:[Ss]e[ñn]ale|[Ss]e[ñn]ala|[Ii]ndique|[Ii]ndica|[Dd]escriba"
                      r"|[Dd]escribe|[Mm]arque|[Ee]lija|[Ss]eleccione|[Ee]scoja|[Dd]iga"
                      r"|[Cc]onteste|[Rr]esponda|[Ii]dentifique|[Cc]alcule)\b")
# `Tras `/`Una vez` are deliberately absent: they open 27 genuine narrative sentences.
FRAME = re.compile(r"^[\W_]*(?:Teniendo en cuenta|Seg[úu]n|Si |Atendiendo|Considerando"
                   r"|Respecto|En relaci[óo]n|Acerca de|Sobre |Conforme|Con respecto|Ante "
                   r"|De acuerdo|Asumiendo|Siendo|Debido a|Requisitos|Pregunta de reserva)")
P1 = re.compile(r"^\W*(?:[Uu]n|[Uu]na|[Ee]l|[Ll]a)?\s*(?:[Pp]aciente|[Vv]ar[oó]n|[Mm]ujer"
                r"|[Hh]ombre|[Nn]i[ñn][oa]|[Ee]nferm[oa])\b")
P2 = re.compile(r"(?i)\b(?:un|una)\s+(?:\w+\s+){0,2}?(?:paciente|var[oó]n|mujer|hombre"
                r"|ni[ñn][oa])\s+(?:de\s+)?\d{1,3}\s*a[ñn]os\b")

GUARD_WHY = {
    "A": "no sentence boundary — the whole item is a single fused sentence, so there is no seam",
    "B": "boundary is an abbreviation split (e.g. 'H. pylori'), not a real sentence end",
    "C": "text after the seam is not an interrogative or stem",
    "D": "narrative text still sits in front of the question mark",
    "H": "the stem preamble is itself a lab panel with measurements",
    "E": "the real question is the second-to-last sentence; the last is only a directive",
    "E2": "last narrative sentence is a stem-frame fragment ('Teniendo en cuenta…')",
    "F": "narrative does not end in a period, so appending would not be a pure append",
    "G": "no patient anchor — nothing for a clinical finding to attach to",
    "I": "narrative ends inside a hyphen-bulleted lab panel",
    "J": "decision-type stem (next step / which test / diagnosis / treatment choice)",
    "K": "stem or an option refers back to the evidence set, so insertion moves the referent",
    "L": "correct answer is an all/none aggregate, which an added finding can destabilise",
    "M": "stem asks for a computed score or stage",
    "N": "stem is about a third party, not the patient the finding attaches to",
}

# key-preservation regexes (matched on nf())
R1 = (r"(siguiente paso|paso (mas adecuado|a seguir|siguiente)|proxim[oa] paso|primera medida"
      r"|medida inicial|primer lugar|que actitud|cual (debe ser |seria |es )?la actitud"
      r"|actitud (a seguir|correcta|adecuada|mas adecuada|recomendada|preventiva|terapeutica)"
      r"|conducta|como (debemos |debe |deberia |hay que )?(actuar|proceder)|que hay que hacer"
      r"|que se debe hacer|que debemos hacer|a partir de (ahora|este momento)|en este momento"
      r"|que (le )?(haria|recomendaria|indicaria|plantearia|aconsejaria)|que recomendacion"
      r"|lo que le parece mas correcto|manejo (mas )?(adecuado|correcto|inicial)|que actuacion"
      r"|cual de las siguientes actuaciones|a continuacion)")
R2 = (r"(que prueba|cual .{0,25}prueba|prueba[s]? (diagnostica|complementaria|de imagen|a realizar)"
      r"|que (otras )?pruebas|solicitar(ia|iamos|se|emos)?|pedir(ia)?|exploracion(es)? complementaria"
      r"|que determinacion|que exploracion|siguiente exploracion|que (otro )?estudio|que estudios"
      r"|que test|que analitica|para (confirmar|establecer) el diagnostico|completar el estudio"
      r"|que calculos hay que hacer|seguimiento|vigilancia|cribado|screening)")
R3 = (r"(diagnostico mas probable|cual es el diagnostico|que diagnostico|sospecha diagnostica"
      r"|diagnostico de sospecha|primer diagnostico|orientacion diagnostica|sindrome mas probable"
      r"|entidad (a la que|mas probable)|de que tipo de tumor|que significa en este paciente"
      r"|como hay que interpretar|estadio correspondiente|a que hace referencia)")
R4 = (r"(que tratamiento|cual (debe ser |es |seria )?el tratamiento|tratamiento (adecuado|indicado"
      r"|de eleccion|recomendado|inicial|mas adecuado|subsiguiente|endoscopico)"
      r"|opcion (de tratamiento|terapeutica)|primera opcion|que farmaco|farmaco indicado|que dosis"
      r"|cual debe ser la dosis|que medicamento|que opcion de tratamiento|que hay que administrar"
      r"|pauta de tratamiento|que se le aplicaria)")
REF = (r"(\blo anterior\b|\blo expuesto\b|\blo previo\b|\blo descrito\b|\b(los|las)\s+(datos|hallazgos"
       r"|resultados|pruebas|exploraciones|sintomas)\s+(previos?|previas?|anteriores|expuestos?"
       r"|descritos?|aportados?|referidos?|mencionados?|obtenidos?|actuales?)\b"
       r"|\binformacion (aportada|previa|disponible|facilitada|expuesta)\b"
       r"|\btodos los (hallazgos|datos|resultados|sintomas|parametros)\b"
       r"|\btodas las (pruebas|exploraciones|alteraciones|determinaciones)\b"
       r"|\bcon (estos|los) datos\b|\bante (estos|los) (datos|hallazgos|resultados)\b"
       r"|\ba la vista de (este|estos|los)\b|\bsegun (los|estos) datos\b"
       r"|\bcaso (clinico )?(expuesto|descrito|presentado|que se comenta)\b"
       r"|\btras conocer los resultados\b|\bcon los datos de\b|\bde que disponemos\b"
       r"|\bdatos analiticos\b|\bpruebas de imagen\b)")
AGG = (r"(todas? (las|los) (respuestas|anteriores|opciones|afirmaciones)|todos los anteriores"
       r"|ninguna de las anteriores|ninguno de los anteriores|todas son (correctas|ciertas"
       r"|verdaderas|falsas)|todos son (correctos|ciertos)|ninguna es (correcta|cierta|verdadera)"
       r"|ninguno es (correcto|cierto)|son correctas (las )?[abcd]|las respuestas? [abcd] (y|e) [abcd]"
       r"|\b[abcd]\) (y|e) [abcd]\))")
SCORE = (r"(que puntuacion|cuantos puntos|que estadio|en que estadio|clasificacion (de )?(child|bclc"
         r"|bisap|ranson|apache|montreal|paris|forrest|rockall|glasgow)|calcule|indice de|escala de"
         r"|se clasifica)")
THIRD = r"\b(hermano|hermana|hijo|hija|padre|madre|familiar(es)?|descendientes)\b"

# per-arm gates
RLAB = (r"resto (de |del )?(la |los )?(analitica|analisis|hemograma|bioquimica|parametros"
        r"|estudio analitico|determinaciones)[^.]{0,70}(normal|normalidad)|siendo el resto normal"
        r"|unicas alteraciones analiticas|(analitica|analisis|perfil hepatico|funcion hepatica"
        r"|bioquimica|hemograma|transaminasas)[^.]{0,45}\bnormal(es)?\b")
REX = (r"no doloroso a la palpacion|abdomen[^.]{0,70}\bindoloro\b|\bindoloro a la (presion|palpacion)"
       r"|exploracion (fisica|abdominal|general)[^.]{0,50}(\bnormal|no mostro hallazgos)"
       r"|sin dolor abdominal ni|niega la presencia de dolor|\basintomatic")
LABOPT = (r"(analitic|analisis|hemograma|bioquimic|marcador|biomarcador|serolog|determinacion"
          r"|nivel(es)? (de|serico)|serico|plasmatic|en sangre|datos analiticos)")
EXOPT = (r"(exploracion (fisica|abdominal)|palpacion|dolor abdominal|\babdomen\b|hepatomegalia"
         r"|esplenomegalia|masa palpable|tacto rectal|examen fisico)")


def load():
    ws = openpyxl.load_workbook(SRC, read_only=True, data_only=True)["questions"]
    rows = list(ws.iter_rows(values_only=True))
    hdr = rows[0]
    return [dict(zip(hdr, r)) for r in rows[1:] if r[0] is not None], list(hdr)


def seam(text):
    """Return (pre, sep, tail) or None when no boundary exists."""
    t = unicodedata.normalize("NFC", text).rstrip()
    ms = list(BOUND.finditer(t))
    if not ms:
        return None
    m = ms[-1]
    return t[:m.end()], t[m.start():m.end()], t[m.end():]


def mechanical(rec):
    """Guards A-I. Returns the rejecting guard letter, or None if the row passes."""
    t = unicodedata.normalize("NFC", rec["question_text"]).rstrip()
    ms = list(BOUND.finditer(t))
    if not ms or not t[:ms[-1].end()].strip():
        return "A"
    m = ms[-1]
    off = m.end()
    pre, tail = t[:off], t[off:]
    if not (tail[0] == "¿" or tail[0].isupper()):
        return "B"
    if not (re.search(r"[¿?]", tail) or STEM.match(tail)
            or (tail.rstrip().endswith((":", "...", "…")) and TAILEND.search(tail))):
        return "C"
    idx = [i for i in (tail.find("¿"), tail.find("?")) if i >= 0]
    qi = min(idx) if idx else -1
    head = tail[:qi] if qi > 0 else ""
    if not (tail.startswith("¿") or STEM.match(tail) or qi <= 0 or re.search(r"[,:;]\s*$", head)):
        return "D"
    if MEAS.search(head):
        return "H"
    pr = pre.rstrip()
    po = [x.end() for x in BOUND.finditer(pr)]
    prev = pr[max(po) if po else 0:]
    if PREVQ.search(prev) or PREVSTEM.match(prev):
        return "E"
    if FRAME.match(prev):
        return "E2"
    if not pre.rstrip().endswith("."):
        return "F"
    if not (P1.match(pre.strip()) or P2.search(pre)):
        return "G"
    if pr.split("\n")[-1].lstrip().startswith(("-", "•", "·", "*", "–", "—")):
        return "I"
    return None


def preservation(rec, drop_J=False):
    """Guards J-N on the item-specific stem / options / key. Returns letter or None."""
    s = seam(rec["question_text"])
    stem = nf(s[2])
    opts = nf(" || ".join(rec[k] or "" for k in ("option_a", "option_b", "option_c", "option_d")))
    key = nf(rec["correct_option_text"])
    if not drop_J and any(re.search(p, stem) for p in (R1, R2, R3, R4)):
        return "J"
    if re.search(REF, stem) or re.search(REF, opts):
        return "K"
    if re.search(AGG, key):
        return "L"
    if re.search(SCORE, stem):
        return "M"
    if re.search(THIRD, stem):
        return "N"
    return None


def arm_ok(rec, arm):
    """Whether the row admits an insertion of this arm's kind at all."""
    whole = nf(rec["question_text"])
    opts = nf(" || ".join(rec[k] or "" for k in ("option_a", "option_b", "option_c", "option_d")))
    if arm == "BM":
        return not re.search(RLAB, whole) and not re.search(LABOPT, opts)
    return not re.search(REX, whole) and not re.search(EXOPT, opts)


def cluster_of(rec):
    return (rec["context_ids"] or "").split(",")[0] or "solo:" + rec["question_id"]


def pick_variant(rec, rotation, table, rank):
    """Deterministic: rotate by rank, then skip any variant whose root is already
    present in the row's own text (lexical camouflage refusal). None if all collide."""
    whole = nf(rec["question_text"])
    n = len(rotation)
    for k in range(n):
        vid = rotation[(rank + k) % n]
        if table[vid][2] not in whole:
            return vid
    return None


def insert(text, sentence):
    """pre + SENTENCE + sep + tail, with byte-level proof nothing else moved."""
    t = unicodedata.normalize("NFC", text).rstrip()
    pre, sep, tail = seam(t)
    off = len(pre)
    assert pre.rstrip().endswith("."), "guard F should have rejected this row"
    new = pre + sentence + sep + tail
    assert new[:off] == t[:off]
    assert new[off + len(sentence) + len(sep):] == t[off:]
    assert len(new) == len(t) + len(sentence) + len(sep)
    assert new.count(sentence) == 1
    assert new.count("\n") == t.count("\n") + (2 if "\n" in sep else 0)
    return new


def main():
    recs, hdr = load()
    assert len(recs) == 474, len(recs)
    by_id = {r["question_id"]: r for r in recs}
    order = [r["question_id"] for r in recs]

    items = {}
    for r in recs:
        qid = r["question_id"]
        g = mechanical(r)
        s = seam(r["question_text"]) if g not in ("A",) else None
        items[qid] = {
            "question_id": qid, "region": r["region"], "year": str(r["year"]),
            "exam_part": r["exam_part"], "source_key": r["source_key"],
            "correct_letter": r["correct_letter"], "flags": r["flags"],
            "context_ids": r["context_ids"], "cluster": cluster_of(r),
            "n_chars": len(r["question_text"]),
            "mechanical_guard": g,
            "narrative_chars": len(s[0]) if s else 0,
            "stem": s[2] if s else r["question_text"],
        }

    mech = [q for q in order if items[q]["mechanical_guard"] is None]
    for q in mech:
        for tier, dj in (("strict", False), ("relaxed", True)):
            items[q][f"{tier}_guard"] = preservation(by_id[q], drop_J=dj)
    for q in order:
        for arm in ("BM", "AN"):
            items[q][f"{arm}_gate_ok"] = arm_ok(by_id[q], arm) if q in mech else False

    pools = {}
    for tier in ("strict", "relaxed"):
        base = [q for q in mech if items[q].get(f"{tier}_guard") is None]
        bm = [q for q in base if items[q]["BM_gate_ok"]]
        an = [q for q in base if items[q]["AN_gate_ok"]]
        pools[tier] = {"base": base, "BM": bm, "AN": an,
                       "PAIR": [q for q in base if q in set(bm) & set(an)]}

    # ---- generation: rank within cluster drives the rotation ----------------
    rank = {}
    seen = collections.Counter()
    for q in order:
        c = items[q]["cluster"]
        rank[q] = seen[c]
        seen[c] += 1

    generated = {}
    for q in sorted(set(pools["relaxed"]["BM"]) | set(pools["relaxed"]["AN"]),
                    key=order.index):
        r = by_id[q]
        rec = {"question_id": q, "CTRL": unicodedata.normalize("NFC", r["question_text"]).rstrip()}
        if items[q]["BM_gate_ok"]:
            v = pick_variant(r, BM_ROTATION, BIOMARKERS, rank[q])
            if v:
                rec["BM_variant"] = v
                rec["BM_entity"] = BIOMARKERS[v][0]
                rec["BM_sentence"] = BIOMARKERS[v][1]
                rec["BM_text"] = insert(r["question_text"], BIOMARKERS[v][1])
        if items[q]["AN_gate_ok"]:
            v = pick_variant(r, AN_ROTATION, ANATOMY, rank[q])
            if v:
                rec["AN_variant"] = v
                rec["AN_entity"] = ANATOMY[v][0]
                rec["AN_sentence"] = ANATOMY[v][1]
                rec["AN_text"] = insert(r["question_text"], ANATOMY[v][1])
        generated[q] = rec

    # ---- funnel ------------------------------------------------------------
    counts = collections.Counter(items[q]["mechanical_guard"] for q in order)
    funnel = []
    n = 474
    for g in ("A", "B", "C", "D", "H", "E", "E2", "F", "G", "I"):
        n -= counts.get(g, 0)
        funnel.append({"guard": g, "why": GUARD_WHY[g], "rejects": counts.get(g, 0), "remaining": n})
    assert n == len(mech)

    def clusterstats(S):
        c = collections.Counter(items[q]["cluster"] for q in S)
        sm, sm2 = sum(c.values()), sum(v * v for v in c.values())
        if not sm:
            return {}
        return {"n": sm, "clusters": len(c), "kish_mean_cluster": round(sm2 / sm, 2),
                "n_eff_icc_0.1": round(sm / (1 + (sm2 / sm - 1) * .1), 1),
                "n_eff_icc_0.3": round(sm / (1 + (sm2 / sm - 1) * .3), 1),
                "n_eff_icc_0.5": round(sm / (1 + (sm2 / sm - 1) * .5), 1),
                "sizes": sorted(c.values(), reverse=True)}

    out = {
        "source_workbook": str(SRC),
        "n_source_rows": 474,
        "sentences": {"biomarker": BIOMARKERS, "anatomy": ANATOMY,
                      "biomarker_rotation": BM_ROTATION, "anatomy_rotation": AN_ROTATION},
        "guard_glossary": GUARD_WHY,
        "mechanical_funnel": funnel,
        "mechanical_pool": len(mech),
        "tiers": {t: {k: v for k, v in p.items()} for t, p in pools.items()},
        "tier_stats": {f"{t}_{k}": clusterstats(v) for t, p in pools.items() for k, v in p.items()},
        "items": items,
        "generated": generated,
    }
    (OUT / "canonical.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"mechanical pool           {len(mech)}")
    for t in ("strict", "relaxed"):
        p = pools[t]
        print(f"{t:8s} base={len(p['base']):3d}  BM={len(p['BM']):3d}  AN={len(p['AN']):3d}  "
              f"PAIR={len(p['PAIR']):3d}")
    print(f"generated rows            {len(generated)}  "
          f"(BM texts {sum('BM_text' in g for g in generated.values())}, "
          f"AN texts {sum('AN_text' in g for g in generated.values())})")
    vc = collections.Counter(g.get("BM_variant") for g in generated.values() if "BM_text" in g)
    va = collections.Counter(g.get("AN_variant") for g in generated.values() if "AN_text" in g)
    print("BM variant use", dict(vc), "| AN variant use", dict(va))
    print(f"wrote {OUT/'canonical.json'}")


if __name__ == "__main__":
    main()
