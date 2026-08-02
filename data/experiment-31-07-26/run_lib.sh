#!/bin/zsh
# Shared helpers for the 2026-07-31 experiment runs.
#
# A single `medrag-eval run` never completes a dataset: GIFT sheds load and returns
# transient errors, so calls must be retried until the harness itself reports the run
# clean. Convergence is gated on `medrag-eval status`, never on a hand-written SQL
# query -- a call that dies before producing a parsed_answers row is invisible to any
# query that joins that table.

set -u

REPO=/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq
EXPDIR="$REPO/data/experiment-31-07-26"
DB="$EXPDIR/experiment.sqlite"
BIN=/private/tmp/claude-501/-Users-ernestsaenz-Programming-GIFT-abstract-dossier/a0613478-db50-4bbd-ba89-911fee14cc09/scratchpad/freshenv/bin/medrag-eval

# MUST run from the repo root: config._load_dotenv() reads Path.cwd()/".env", so any
# other cwd silently yields no GIFT_API and no OPENROUTER_API_KEY, and every call fails
# with "Request URL is missing an 'http://' or 'https://' protocol".
cd "$REPO" || exit 1
[[ -f "$REPO/.env" ]] || { echo "FATAL: $REPO/.env not found"; exit 1; }

DATASET_A=balanced_a_310726
DATASET_B=balanced_b_310726

# Same four models on both arms, so the arms are directly comparable. The two slowest
# GIFT models (qwen3.6-27b ~61s, gemma-4-31b-it ~39s) are excluded to keep the
# serialised arm inside a feasible wall-clock.
MODELS=(
  google/gemini-3.6-flash
  z-ai/glm-5.2
  qwen/qwen3.6-35b-a3b
  google/gemma-4-26b-a4b-it
)
OR_MODELS=("${MODELS[@]}")
GIFT_MODELS=("${MODELS[@]}")

status_line() {
  "$BIN" status --experiment-name "$1" --db "$DB" 2>&1 | grep -E '^planned=' | head -1
}

# Echoes the status line; returns 0 only when the harness reports the run complete.
is_converged() {
  local line planned completed apif parsef
  line=$(status_line "$1")
  [[ -z "$line" ]] && { echo "   (no status line yet)"; return 1; }
  echo "   $line"
  planned=$(echo "$line"   | sed -n 's/.*planned=\([0-9]*\).*/\1/p')
  completed=$(echo "$line" | sed -n 's/.*completed=\([0-9]*\).*/\1/p')
  apif=$(echo "$line"      | sed -n 's/.*api_failed=\([0-9]*\).*/\1/p')
  parsef=$(echo "$line"    | sed -n 's/.*parse_failed=\([0-9]*\).*/\1/p')
  [[ "$apif" == "0" && "$parsef" == "0" && "$planned" == "$completed" && "$planned" != "0" ]]
}

# converge <experiment> <max_passes> <run args...>
converge() {
  local exp=$1 maxp=$2; shift 2
  local pass
  for pass in $(seq 1 "$maxp"); do
    echo "########## $exp — pass $pass/$maxp — $(date '+%H:%M:%S') ##########"
    "$BIN" run --experiment-name "$exp" --db "$DB" "$@" 2>&1 | tail -25
    if is_converged "$exp"; then
      echo ">>> $exp CONVERGED after $pass pass(es) — $(date '+%H:%M:%S')"
      return 0
    fi
    echo ">>> $exp not yet complete; retrying"
  done
  echo "!!! $exp did NOT converge in $maxp passes"
  return 1
}
