# Code and database provenance — ab520 incorrect-cell triplicate (runs 2–3)

This note identifies the exact local code state, scripts, environment, and
database chain behind the 1,796-logical-call triplicate replication of the
898 run-1 `strict_correct == 0` cells (SPEC.md, this folder). It was written
by agent 3 (provenance) of the consolidation task and every hash below was
**recomputed independently on 2026-08-07** against the files as they sit on
disk in this working tree — none are copied from a manifest without
verification.

Repository root:

```text
/Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq
```

Harness path: `code/medrag_eval/`.

## 1. Input artefact hashes — recomputed vs. `manifests/preparation-summary.json`

Command used for every row: `shasum -a 256 <path>`, run from the repository
root on 2026-08-07.

| Role | Path | SHA-256 (recomputed) | vs. `preparation-summary.json` |
| --- | --- | --- | --- |
| Source run-1 CSV (6000 cells) | `data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/exports/benchmark-6000-cell-results-adjusted.csv` | `ce91b3f3eb90cd0b125a170a6f0a0a967c02d63da17cfa97161e62f739c4b721` | **MATCH** (`source_results_sha256`) |
| Frozen replicate ledger CSV | `.../manifests/frozen-replicate-cell-ledger.csv` | `026bab787956cbe421fe1b380a5250beea0951f226e834a550b2b8cf153b3530` | **MATCH** (`ledger_sha256`) |
| `preparation-summary.json` itself | `.../manifests/preparation-summary.json` | `10eb9cb283364ddb96c23e6e1087a53f2f92172047523c62c64476ae3bd71895` | n/a — this is the manifest; it does not hash itself |
| Pre-execution DB snapshot | `.../manifests/ab520-incorrect-cell-triplicates.pre-execution.sqlite` | `823f92e01d9526e51204eb0fe082d69d8aa4e216830bd6b32d0cef0881ca3d6f` | **MATCH** (`pre_execution_snapshot_sha256`, and equal to `database_sha256` — see §3) |
| Condition A input CSV | `.../inputs/adjusted-500-condition-A.csv` | `6363e298a27a088dc2afdb83d32eec99a3ac7d72945df9c352b312d1c42c6aa9` | **MATCH** (`input_files.A.sha256`) |
| Condition B input CSV | `.../inputs/adjusted-500-condition-B.csv` | `d608ca7e250600407189e18f5cd438e05e63e193c3799751c9e9a79c6672d694` | **MATCH** (`input_files.B.sha256`) |
| Live run DB (post-execution, current disk state) | `.../runs/ab520-incorrect-cell-triplicates-2026-08-05.sqlite` | `6f72be10cdeb00a132ac1ab166527783af64cdbc177f254bac5fff22422a3359` | **DIFFERS** (`database_sha256` = `823f92e0…`, the pre-execution value) — **expected**, see below |

**Why the live DB "DIFFERS" is not a corruption signal.** `preparation-summary.json`
was written at `2026-08-05T16:16:49Z`, *before* any calls were issued, and its
`database_sha256` field records the DB in its empty, freshly-created state —
which is why it is byte-identical to the pre-execution snapshot's hash. The
live DB has since received 1,856 provider attempts, 1,788 parsed answers, and
1,788 scores across five append rounds (see §2 commit list), so its hash
necessarily diverges from the day-zero value. The correct way to read this
row is "the live DB hash no longer equals the pre-execution hash, precisely
because execution wrote to it" — that is confirmation the DB was used, not
evidence against it.

Independent cross-check on the live DB, re-verified 2026-08-07 after `HEAD`
advanced from `7ef8436` to `dd3a6b8` (see §2 — that commit did not touch the
DB file, so this holds unchanged): `git status` shows **zero diff** between
the on-disk file and the blob committed at `HEAD` (`dd3a6b8`) — only two
SQLite journal side-files (`*.sqlite-shm`, `*.sqlite-wal`, both untracked,
both artifacts of the read-only `sqlite3` session opened for this audit)
show as untracked. The committed blob hash is
`e1a6d24a6d2cc34d422611e72a675b7e2273814a` (`git rev-parse
HEAD:.../runs/ab520-incorrect-cell-triplicates-2026-08-05.sqlite`, unchanged
across both commits); disk size 34,721,792 bytes matches the size recorded
in the `7ef8436` diffstat (`Bin 33517568 -> 34721792 bytes`, the commit that
last wrote to this file). The live DB in this working tree is therefore
exactly the DB as last committed — no uncommitted writes, no drift.

## 2. Git commits relevant to this work

`git log --oneline -16` (repository root; first run 2026-08-07 at the start
of this audit, re-run 2026-08-07 later the same day after `HEAD` advanced by
one commit — both runs shown are from the second, current pass):

```
dd3a6b8 Record the real argv in invocation records, not a five-argument template
7ef8436 Complete gemini_B via Google Vertex: 1,788/1,796, the protocol ceiling
2070a96 Allow an experiment to pin the OpenRouter upstream, off by default
ef04b53 Record that no alternative provider can serve gemini under the frozen request
7617826 Record the failed gemini_B resume loop: +2 scored, 5 more cells destroyed
10a8fa3 Record the failed gemini_B retry round and correct the 429 diagnosis
0bf6537 Resume the ab520 triplicate run to 1,695/1,796; TailScale A now 325/326
7571ab7 Checkpoint the ab520 incorrect-cell triplicate run at 1,500/1,796 scored
c7f9613 Add ExpC mechanical-130 addendum and the aug-26 ab520 500-item experiment
9660b9a Add the 2026-07-31 balanced-MCQ A/B experiment and its analysis
```

`HEAD` at the time the facts in §3 were last verified (2026-08-07):
`dd3a6b8688a80bbf0e55c6590ddf9e25d1c2e71d`. **`HEAD` has continued to
advance since**, as this shared consolidation session's coordinator commits
the finished output folder (e.g. `6d11fe6`, "Add the consolidated triplicate
evidence folder for runs 1-3" — which adds this `provenance/` package itself
to git, among other agents' deliverables, and touches none of the source
files this document verifies). Treat every hash and code-reading claim in
this document as anchored to the specific commit named next to it
(`dd3a6b8`, `7ef8436`, `2070a96`, etc.), not to "whatever `HEAD` is" — those
commits, and what they contain, do not change as `HEAD` moves forward.

This commit (`dd3a6b8`) landed **during** this audit: this agent first
hashed `execute_replicates.py` while it was an
uncommitted working-tree edit by another agent (recorded then as
`e8e17d413efe3cce89c6cb6d49635c00b3ac2389df79f19629c451b608eeda27`), then
re-hashed it as a further-edited uncommitted file
(`24109aa200ae4be2d0f1edcfe7e1bda5e45c9023ff25acf40b83c89ee7065b38`), and it
is now committed at `dd3a6b8` with the hash recorded in §3 below. All three
observations are kept here for the audit trail rather than silently
replaced, since each was an accurate snapshot of a real, distinct state of
that file at the time it was taken.

| Commit (full SHA) | Subject | Files touched (this experiment) |
| --- | --- | --- |
| `dd3a6b8688a80bbf0e55c6590ddf9e25d1c2e71d` | Record the real argv in invocation records, not a five-argument template | `execute_replicates.py` (+47/-5 — replaces the 5-flag `redacted_command` template with one derived from real `sys.argv`, adds an explicit `protocol_deviation` field to invocation records); `ledger/LEDGER_README.md` (new, 371 lines — owned by agent 2/ledger, not this agent). Per the commit message, the 34 pre-existing invocation records are deliberately left unmodified (not backfilled), so this fix is prospective only. |
| `7ef843650ffcff3e6a7ffbca06882c0ff2a930cf` | Complete gemini_B via Google Vertex: 1,788/1,796, the protocol ceiling | `STATUS.md`; `execute_replicates.py` (+51 lines, the `provider_routing` opt-in plumbing at the script level); `invocations/or-b-gemini-vertex-{TEST-4cells,run1}.json`; `logs/or-b-gemini-vertex-{TEST-4cells,run1}.jsonl`; the live `.sqlite` (Bin 33517568 → 34721792 bytes) |
| `2070a9609cc1508508ba5d8b72537dcded0a9996` | Allow an experiment to pin the OpenRouter upstream, off by default | `code/medrag_eval/providers/base.py` (+6), `code/medrag_eval/providers/openrouter.py` (+1/-1), `code/medrag_eval/runner.py` (+5/-1) — **the harness change**; no data files touched |
| `ef04b53e6a19274c6a6bfbfb9126a07ca0a0fadf` | Record that no alternative provider can serve gemini under the frozen request | `STATUS.md` only (+33) |
| `7617826b331754e6c8e1b4bf6eba7cff108e5076` | Record the failed gemini_B resume loop: +2 scored, 5 more cells destroyed | `STATUS.md`; `invocations/or-b-gemini-resume3-r{1..6}.json`; `logs/or-b-gemini-resume3-r{1..6}.jsonl`; the live `.sqlite` (Bin 33378304 → 33517568 bytes) |
| `10a8fa356b6f79c6e939a3bc4736a3bfdb70d3ac` | Record the failed gemini_B retry round and correct the 429 diagnosis | `STATUS.md`; `invocations/or-b-gemini-probe-b101-r2-retry2.json`, `invocations/or-b-gemini-r2-r3-resume2.json`, `invocations/ts-a-glm-probe-b264-retry4.json` + matching `logs/*.jsonl`; the live `.sqlite` (Bin 33349632 → 33378304 bytes) |
| `0bf65371a012f8eaaf3ec3f34eb4656759b9e65a` | Resume the ab520 triplicate run to 1,695/1,796; TailScale A now 325/326 | `STATUS.md`; multiple `invocations/ts-a-*.json` and `invocations/or-b-gemini-probe-b101-r2-20260806.json` + matching `logs/*.jsonl` |
| `7571ab7024ebf97378de825a66ed2281f878bff3` | Checkpoint the ab520 incorrect-cell triplicate run at 1,500/1,796 scored | `README.md`, `STATUS.md`, `execute_replicates.py` (new, 586 lines), `prepare_replicates.py` (new — introduced here, alongside `execute_replicates.py`), `inputs/adjusted-500-condition-{A,B}.csv`, and the bulk of the `invocations/*.json` / `logs/*.jsonl` set |
| `c7f96131485671a406485d4d73987c0b0481fca5` | Add ExpC mechanical-130 addendum and the aug-26 ab520 500-item experiment | Base commit that produced `exports/benchmark-6000-cell-results-adjusted.csv` (the run-1 source), among many other `data/experiment-4-aug-26/` files. Not part of this replication's own history but is the run-1 result the replication reads. |
| `9660b9a503cf68c45b9a808f38ba597b41769c16` | Add the 2026-07-31 balanced-MCQ A/B experiment and its analysis | Unrelated prior experiment; listed because it appears in the 15-commit window. Not a dependency of this replication. |

`prepare_replicates.py` and `manifests/preparation-summary.json` /
`manifests/frozen-replicate-cell-ledger.csv` /
`manifests/ab520-incorrect-cell-triplicates.pre-execution.sqlite` were all
introduced together in `7571ab7` — there is no separate "prepare" commit.

## 3. Exact code version — the `provider_routing` mechanism

Current repository state, re-checked 2026-08-07 after `HEAD` advanced to
`dd3a6b8`: `git status --short code/medrag_eval/` returns nothing — the
harness directory has **no local modifications**, working tree matches
`HEAD` (`dd3a6b8`) there (unaffected by that commit, which touched only
`execute_replicates.py` and a new `ledger/LEDGER_README.md`, neither inside
`code/medrag_eval/`). (Elsewhere in the repo, outside this provenance
package's remit, `git status` continues to show unrelated deletions of
top-level files such as `README.md`/`LICENSE`/`CITATION.cff` and other
uncommitted changes belonging to other agents' work in this shared session;
re-observed at both checkpoints of this audit, unchanged in substance
between them. Reported here for completeness — not part of this
replication's code path, and this agent made no changes outside
`provenance/`.)

Read directly from the files at `HEAD`:

- **`code/medrag_eval/providers/base.py:74`** — `ProviderRequest.provider_routing:
  dict[str, Any] | None = None`. The field is documented in-line (lines
  69–74): `None` keeps the adapter's previous hardcoded default of
  `{"require_parameters": True}`; setting it is reserved for a "deliberate,
  documented protocol deviation" because `require_parameters` is an
  integrity guarantee (it makes OpenRouter refuse any upstream that would
  silently drop `temperature`/`top_p`), not a routing preference.
- **`code/medrag_eval/providers/openrouter.py:176`**, inside
  `_chat_payload`: `"provider": request.provider_routing or
  {"require_parameters": True}`. **Confirmed by direct reading**: when
  `provider_routing` is `None` (the default and the value used for every
  cell except the 91 Vertex-routed gemini_B cells), this expression
  evaluates to the exact same literal dict OpenRouter payloads carried
  before the change — the previous behavior is reproduced byte-for-byte.
- **`code/medrag_eval/runner.py:590,604`** (`_execute_call`) and
  `:622,666` (`_execute_call_with_conn`) — `provider_routing` is accepted as
  a keyword-only parameter defaulting to `None` and threaded straight into
  the `ProviderRequest` constructed for each call. Line 666 is the load-
  bearing guard: `provider_routing=None if is_tailscale else
  provider_routing` — TailScale calls get `None` unconditionally regardless
  of what the caller passed, matching the base.py docstring's "TailScale
  ignores this field."

Net effect, confirmed by code reading rather than assumed from the commit
message: every cell in this replication used the untouched default
(`provider_routing=None`) **except** the 91 gemini_B cells the executor
explicitly pinned to `google-vertex` after `2070a96` landed (see §2, and
`DEVIATIONS`/SPEC.md's protocol-deviation section for the authorization
trail). TailScale (`tailscale_A`) cells could not have been affected by this
field under any caller input, by construction of line 666.

- Pre-existing, unrelated to this change: `ruff` reports `F821` for an
  undefined `ParseResult` annotation at `runner.py:765`, called out in the
  `2070a96` commit message as present in `HEAD` before that change (not
  re-verified independently here; recorded for completeness).
- Prompt version: `mcq_es_v4`. Temperature: `0` (declared; silently
  overridden by Vertex for the 91 affected cells — see SPEC.md protocol
  deviation section). GIFT/TailScale prompt ID: `13`.

### Replication-local orchestration scripts

Workspace files, not part of the `code/medrag_eval/` package, both
introduced in `7571ab7`. Current hashes, re-verified 2026-08-07 against the
now-committed `dd3a6b8` state (`git status --short` on both paths returns
nothing — disk matches `HEAD` exactly, zero uncommitted diff):

| Role | Path | SHA-256 (current, `HEAD` = `dd3a6b8`) |
| --- | --- | --- |
| Prepare frozen replicate execution inputs | `data/experiment-4-aug-26/replications/ab520-incorrect-cells-triplicate-2026-08-05/prepare_replicates.py` | `03df9bfbee2010e8d84b21f6f162445e6f9ef77aacd7e523e2e312f2f3c4f6ae` (unmodified since first recorded) |
| Issue and record replicate calls (runs 2–3, incl. the `provider_routing` pin used for the Vertex round) | `data/experiment-4-aug-26/replications/ab520-incorrect-cells-triplicate-2026-08-05/execute_replicates.py` | `8b5e4306ad7af988339903aa58412cd460fc43f3874065bce6370993788f60c2` |

Neither script has a hash recorded in `preparation-summary.json` to check
against (that manifest records data/DB hashes only, not script hashes), so
these rows are first-recorded here, not a MATCH/DIFFERS comparison.

**Chain of custody for `execute_replicates.py`'s hash, kept in full because
it changed twice during this audit and each value was a true snapshot at
the time it was taken:**

1. `e8e17d413efe3cce89c6cb6d49635c00b3ac2389df79f19629c451b608eeda27` —
   this agent's first hash, taken before any edit, matching the version
   `7ef8436` last committed.
2. `24109aa200ae4be2d0f1edcfe7e1bda5e45c9023ff25acf40b83c89ee7065b38` —
   recorded when another agent's edit was still uncommitted working-tree
   state.
3. `8b5e4306ad7af988339903aa58412cd460fc43f3874065bce6370993788f60c2` —
   **current.** That edit is now commit `dd3a6b8` (§2); this hash matches
   both the committed blob and the on-disk file exactly.

The change itself (`git show dd3a6b8`) touches only `write_invocation`'s
recorded metadata, not call-execution logic or the
`provider_routing`/`--deviation-route-upstream` mechanism:

1. A new `_redacted_command()` helper reconstructs `redacted_command` from
   the real `sys.argv` (redacting path-shaped tokens) instead of a
   hand-built f-string that only listed 5 fixed flags. The old template
   could not represent an invocation using `--question-id`, `--run-index`,
   or `--deviation-route-upstream` faithfully; the new version can.
2. A new `protocol_deviation` field is added to the invocation record,
   explicitly `null` when `--deviation-route-upstream` was not passed and a
   structured object (`upstream_override`, `require_parameters: false`,
   `allow_fallbacks: false`, consequence note) when it was.

Net effect, confirmed by the commit message: this is a **recording-fidelity
fix for future invocations**, not a change to how the 1,796 frozen calls
already in the live DB were executed — the commit explicitly leaves the 34
`invocations/*.json` files already committed (§2) unmodified, since they
were written by the pre-edit code and rewriting a record to say something it
did not say would defeat its purpose. The limitation is instead documented
in `ledger/LEDGER_README.md` (new in `dd3a6b8`, owned by agent 2/ledger —
not reproduced here).

## 4. Python / uv environment

Run 2026-08-07 from the repository root:

```text
$ uv run python --version
Python 3.14.4
```

Key resolved package versions (`uv run python -c "import importlib.metadata
as m; print(m.version('<pkg>'))"`):

| Package | Version | Note |
| --- | --- | --- |
| `httpx` | `0.28.1` | HTTP client; `pyproject.toml` pins `>=0.27` |
| `pydantic` | `2.13.4` | `ProviderRequest`/`ProviderResponse` dataclasses live alongside pydantic models in this package; `pyproject.toml` pins `>=2` |
| `requests` | not installed / no package metadata found | not a declared dependency (`pyproject.toml` lists `httpx`, `openpyxl`, `pydantic`, `python-dotenv`, `rich`, `typer` as core deps) |
| `sqlite-utils` | not installed / no package metadata found | not a declared dependency; DB access in this package goes through the stdlib `sqlite3` module |

`pyproject.toml` declares `requires-python = ">=3.11"`; the resolved
interpreter (3.14.4) satisfies that. Core dependencies per `pyproject.toml`:
`httpx>=0.27`, `openpyxl>=3.1`, `pydantic>=2`, `python-dotenv>=1`, `rich>=13`,
`typer>=0.12`.

## 5. Related files in this package

- `provenance/INTEGRITY_CHECKS.md` — the executed integrity queries and
  their results. Two figures in an earlier SPEC.md draft (the multi-hash
  logical-call count and the invocation/log file counts) were caught as
  disagreements during this audit and have since been corrected in SPEC.md;
  §6 and §8 of that file record the finding and its resolution.
- `provenance/DATA_DICTIONARY.md` — full schema of the live run DB and the
  run-1 CSV-to-schema mapping.
