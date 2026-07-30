# medrag-eval

`medrag-eval` is a CLI-only benchmark harness for Spanish gastroenterology
multiple-choice questions against the TailScale Medical RAG API and OpenRouter.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Fill `.env` locally. Do not commit secrets, database files, raw responses, or
exports.

The four credential variables are required. `MEDRAG_EVAL_DB` is an optional
override for the local SQLite database path (default: `./runs/medrag_eval.sqlite`);
set it only if you need a non-default location.

`.env` and `.env.example` are dotfiles, so they are hidden by a normal `ls`.
Use `ls -la` from the project root to see them.

Optional report generation dependencies are separate from the core CLI:

```bash
python -m pip install -e '.[reports]'
```

## Typical Workflow

```bash
medrag-eval init-db
medrag-eval import-questions /path/to/questions-first-50.xlsx --dataset galicia_2016_digestivo
medrag-eval run --dataset galicia_2016_digestivo --providers tailscale,openrouter --models medical-rag,google/gemini-3-flash-preview --runs 1 --limit 2 --experiment-name smoke002 --dry-run
medrag-eval status --experiment-name smoke002
medrag-eval export --experiment-name smoke002 --format csv
```

Every GIFT/TailScale benchmark request is pinned to the stored multiple-choice
prompt with `X-Prompt-ID: 13`. The runner applies ID 13 automatically and rejects
any other value; `--tailscale-prompt-id 13` may be supplied explicitly.

The benchmark workbook is intentionally not committed. Place it locally and pass
its path to `import-questions`. The original `questions-first-50.xlsx` contains
50 workbook rows. Rows `g25` and
`g38` are annulled and do not have a scoreable gold answer, so import skips them
with warnings. A `--limit 50` run over this dataset plans 48 scoreable questions.
