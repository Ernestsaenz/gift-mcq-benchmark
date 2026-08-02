#!/bin/zsh
# OpenRouter arm: 6 models. Experiment A to convergence, then Experiment B.
source "$(dirname "$0")/run_lib.sh"

ARGS_A=(); for m in $OR_MODELS; do ARGS_A+=(--provider-model "openrouter:$m"); done
ARGS_B=("${ARGS_A[@]}")

echo "===== OPENROUTER ARM start $(date) ====="
converge expA_or_310726 12 --dataset "$DATASET_A" --runs 1 "${ARGS_A[@]}" || exit 1
echo
converge expB_or_310726 12 --dataset "$DATASET_B" --runs 1 "${ARGS_B[@]}" || exit 1
echo "===== OPENROUTER ARM done $(date) ====="
