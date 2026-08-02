#!/bin/zsh
# Experiment B on the OpenRouter arm, launched independently of A.
# A is 1895/1896 complete; its single outstanding call (b320 x glm-5.2) is a
# deterministic finish_reason=length runaway that has failed 5/5 attempts, so B is
# started in parallel rather than waiting on it.
source "$(dirname "$0")/run_lib.sh"
ARGS=(); for m in $OR_MODELS; do ARGS+=(--provider-model "openrouter:$m"); done
echo "===== OPENROUTER B start $(date) ====="
converge expB_or_310726 12 --dataset "$DATASET_B" --runs 1 "${ARGS[@]}"
echo "===== OPENROUTER B done $(date) ====="
