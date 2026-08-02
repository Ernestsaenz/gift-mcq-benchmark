#!/bin/zsh
# GIFT arm: 4 models, SERIALISED (--tailscale-concurrency 1).
# Concurrency >1 makes GIFT shed load and return errors as HTTP 200 bodies (~63% rate).
# Experiment A must fully converge before Experiment B starts.
source "$(dirname "$0")/run_lib.sh"

ARGS=(); for m in $GIFT_MODELS; do ARGS+=(--provider-model "tailscale_medical_rag:$m"); done

echo "===== GIFT ARM start $(date) ====="
converge expA_gift_310726 40 --dataset "$DATASET_A" --runs 1 "${ARGS[@]}" --tailscale-concurrency 1 || exit 1
echo
converge expB_gift_310726 40 --dataset "$DATASET_B" --runs 1 "${ARGS[@]}" --tailscale-concurrency 1 || exit 1
echo "===== GIFT ARM done $(date) ====="
