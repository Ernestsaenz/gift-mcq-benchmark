#!/bin/zsh
# Three more passes at expA_or_310726. Resume skips the 1895 completed cells and
# retries only b320 x glm-5.2. Cannot target it with --question-id: that flag is part
# of the experiment run config (runner.py:184-190) and would trip _validate_experiment_reuse.
source "$(dirname "$0")/run_lib.sh"
ARGS=(); for m in $OR_MODELS; do ARGS+=(--provider-model "openrouter:$m"); done
converge expA_or_310726 3 --dataset "$DATASET_A" --runs 1 "${ARGS[@]}"
echo "===== A retry finished $(date) ====="
