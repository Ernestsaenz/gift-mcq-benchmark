# Independent QA report

Audit date: 2026-08-04  
Auditor role: independent QA subagent with read-only instructions  
Candidate-slate verdict: **PASS — 22/22 PASS, 0 FAIL, 0 UNCERTAIN**  
Execution verdict: **NOT READY — protocol review gates remain open**

The auditor checked the pinned workbook rows, official exam and definitive-key evidence, medical correctness, Condition A and exact-swap Condition B semantics, semantic overlap with the retained 478 questions, rendered GIFT inputs, the proposed 500-question benchmark, the 264-cell run matrix, package checksums, and canonical-file immutability. The audit used the official keys and therefore is independent but not blinded; it does not count toward the protocol's blinded-QA requirement.

## Per-candidate verdicts

| Map | Replacement | Key | Independent content finding | Verdict |
|---|---|---:|---|---|
| r001 | n169 → c2485 | D | Hepatopulmonary syndrome is associated with increased pulmonary/exhaled nitric oxide. | PASS |
| r002 | b320 → c2718 | D | An intraduodenal distal-common-bile-duct choledochocele is Todani type III. | PASS |
| r003 | n031 → c0205 | D | Coagulopathy is the clear admission criterion in acute hepatitis. | PASS |
| r004 | b199 → c0211 | D | An 8-mm, R0, G1 appendiceal NET is adequately treated by appendectomy. | PASS |
| r005 | b248 → c2116 | D | The right anterosuperior Couinaud segment is VIII. | PASS |
| r006 | b260 → c2027 | B | Pyoderma gangrenosum can follow minor trauma through pathergy. | PASS |
| r007 | b141 → c2132 | D | Fructose/sorbitol malabsorption can contribute to IBS symptoms. | PASS |
| r008 | b142 → c2644 | C | The described middle-esophageal lesion and histology indicate squamous carcinoma. | PASS |
| r009 | b143 → c0922 | B | Gastric schwannoma is characteristically S100-positive and c-KIT-negative. | PASS |
| r010 | b147 → c0381 | B | The encapsulated solid-cystic pancreatic mass is a solid pseudopapillary tumor. | PASS |
| r011 | b148 → c0177 | B | Fasting-persistent secretory diarrhea plus a pancreatic mass is consistent with VIPoma. | PASS |
| r012 | b151 → c0248 | B | Kudo pit-pattern assessment requires magnification. | PASS |
| r013 | b153 → c2600 | D | Alpha-1 antitrypsin deficiency has codominant inheritance. | PASS |
| r014 | b154 → c0955 | C | The described early interstitial-pancreatitis collection is an acute peripancreatic fluid collection. | PASS |
| r015 | b155 → c2647 | C | Glasgow-Blatchford includes blood urea, unlike the distractor variables. | PASS |
| r016 | b156 → c2033 | C | A nonbleeding visible vessel is Forrest IIa. | PASS |
| r017 | b157 → c0931 | C | Montreal E2 denotes left-sided ulcerative colitis. | PASS |
| r018 | b158 → c2443 | B | Rome IV functional bloating requires insufficient criteria for the listed alternative disorders. | PASS |
| r019 | b159 → c0973 | C | FIB-4 uses age, AST, ALT, and platelet count. | PASS |
| r020 | b160 → c2714 | D | Zinc treats Wilson disease by blocking intestinal copper absorption. | PASS |
| r021 | b161 → c0369 | B | Perforation is the absolute contraindication to colonic SEMS placement. | PASS |
| r022 | b163 → c2093 | C | Daughter vesicles strongly identify a hepatic hydatid cyst. | PASS |

Related-topic pairs were reviewed and accepted as distinct propositions: c2027/n080, c2132/c2443, c0922/b366, c0955/n003+n012, c2647/b446+b467, c0931/n083, and c2443/b218.

## Open protocol gates

1. **Blinded QA:** none of the 22 candidates has the required two prior blinded QA PASS records. Seven have one and fifteen have zero, so 37 additional blinded PASS records are required. This audit cannot count because the auditor saw the official keys and A/B transformations.
2. **Formal sourcing:** twelve candidates have a formal sourcing PASS. Ten use `manual_research_adjudication`, which is explicitly research synthesis rather than formal sourcing; those ten require formal sourcing approval or an explicit protocol-owner waiver.
3. **Execution:** every matrix row remains `NOT_RUN_REQUIRES_FINAL_PROTOCOL_QA`. No provider traffic was issued.

## Mechanical and integrity results

- 22/22 workbook rows match their selected source packets.
- 22/22 official evidence records bind to the recorded exam and definitive-key PDF hashes.
- 17/22 normalized exam extractions match exactly; five needed visual confirmation only for OCR artifacts such as Roman numerals and option markers.
- 22/22 questions have four distinct source options and no pre-existing none/aggregate option.
- 22/22 Condition B rows change exactly the keyed option and `correct_option_text`; the answer letter is unchanged.
- 44/44 rendered GIFT prompts match their recorded hashes; maximum length is 675 characters.
- The proposed benchmark contains 500 unique IDs, with 478 retained records object-identical and in their original order plus exactly 22 replacements.
- The run matrix is the exact 22 × 3 arms × 4 models Cartesian product: 264 unique, not-run rows.
- Final package checksums pass for all 15 listed files, including this report.
- Canonical-result verification passed 64/64 all-file hashes, 10/10 output hashes, and 15/15 code-provenance hashes.
- The canonical benchmark SHA-256 remains `057f8b805d928e90079b8ba80b326581e6e14f65fb9a1644a0b4d53cbc294abc`.
- No canonical file was changed and no provider request was made.

## Security note

The builder is standard-library-only and performs no network or provider operations. A Snyk code-scan capability was not exposed in this session, so no Snyk scan was performed.
