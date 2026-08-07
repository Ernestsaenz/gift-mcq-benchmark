# experiment-5 test set — 10 Condition-B hard questions

Source: `data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/analysis/openrouter-b-hardest-200/hardest-200-questions.csv`  (rows already in Condition-B form).

Deterministic selection by `deterministic_rank` within difficulty tier (difficulty = number of the 4 OpenRouter-B models that answered wrong):

- 5 from the 4-wrong core (unanimously wrong)
- 3 from the 3-wrong tier
- 2 from the 2-wrong tier

**Composition** — tiers {4: 5, 3: 3, 2: 2} · correct-letter {'b': 5, 'd': 3, 'c': 2} · negated_stem {'True': 4, 'False': 6} · origin {'retained318': 7, 'new182': 2, 'replacement22_2026-08-04': 1}.

| rank | tier(wrong) | id | source_key | key | negated | wrong models (B) |
|---:|---:|---|---|:--:|:--:|---|
| 1 | 4 | b370 | `castilla-la-mancha|2017|main|84` | b | True | Gemini 3.6 Flash;GLM 5.2;Qwen 3.6 35B;Gemma 4 26B |
| 2 | 4 | b455 | `aragon|2017|main|79` | d | False | Gemini 3.6 Flash;GLM 5.2;Qwen 3.6 35B;Gemma 4 26B |
| 3 | 4 | n088 | `castilla-y-leon|2019|main|43` | b | False | Gemini 3.6 Flash;GLM 5.2;Qwen 3.6 35B;Gemma 4 26B |
| 4 | 4 | b170 | `navarra|2022|caso-clinico-1|95` | d | False | Gemini 3.6 Flash;GLM 5.2;Qwen 3.6 35B;Gemma 4 26B |
| 5 | 4 | b470 | `aragon|2017|reserva-especifica|108` | b | False | Gemini 3.6 Flash;GLM 5.2;Qwen 3.6 35B;Gemma 4 26B |
| 20 | 3 | n111 | `la-rioja|2021|main|8` | b | False | GLM 5.2;Qwen 3.6 35B;Gemma 4 26B |
| 21 | 3 | b184 | `navarra|2022|reserva-casos-clinicos|109` | d | True | GLM 5.2;Qwen 3.6 35B;Gemma 4 26B |
| 22 | 3 | r010 | `andalucia|2022|cuestionario-teorico|74` | b | False | GLM 5.2;Qwen 3.6 35B;Gemma 4 26B |
| 68 | 2 | b284 | `castilla-y-leon|2019|reserva-especifica|158` | c | True | Qwen 3.6 35B;Gemma 4 26B |
| 69 | 2 | b221 | `castilla-la-mancha|2017|main|87` | c | True | GLM 5.2;Qwen 3.6 35B |
