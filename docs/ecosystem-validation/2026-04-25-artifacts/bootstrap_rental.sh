#!/usr/bin/env bash
# pet-infra/docs/ecosystem-validation/2026-04-25-artifacts/bootstrap_rental.sh
# Spec: pet-infra/docs/ecosystem-validation/2026-04-25-design.md §2.1
# Idempotent: 可重复运行；失败立即 exit 1 + step ID

set -euo pipefail

WORKSPACE="${WORKSPACE:-/workspace}"
MATRIX_TAG="2026.10-ecosystem-cleanup"
ORG="https://github.com/Train-Pet-Pipeline"
REPOS=(pet-schema pet-infra pet-data pet-annotation pet-train pet-eval pet-quantize pet-ota pet-id)

declare -A REPO_TAGS=(
  [pet-schema]="v3.2.1"
  [pet-infra]="v2.6.0"
  [pet-data]="v1.3.0"
  [pet-annotation]="v2.1.1"
  [pet-train]="v2.0.2"
  [pet-eval]="v2.3.0"
  [pet-quantize]="v2.1.0"
  [pet-ota]="v2.2.0"
  [pet-id]="v0.2.0"
)

log() { printf '[bootstrap %s] %s\n' "$(date +%H:%M:%S)" "$*" >&2; }
fail() { log "FAIL at step $1: $2"; exit 1; }

# AutoDL 学术加速（仅 github/huggingface；non-China 实例此文件不存在，跳过）
# shellcheck disable=SC1091
[[ -f /etc/network_turbo ]] && source /etc/network_turbo

mkdir -p "$WORKSPACE"
cd "$WORKSPACE"

# 0.0 — 环境基线
log "step 0.0 — env baseline"
disk_gb=$(df -BG . | awk 'NR==2 {gsub(/G/, "", $4); print $4+0}')
[[ "$disk_gb" -ge 150 ]] || fail "0.0" "disk free ${disk_gb}G < 150GB required"
nvidia-smi >/dev/null || fail "0.0" "nvidia-smi failed"
python_ver=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "missing")
log "  python: $python_ver"
[[ -n "${GH_TOKEN:-}" ]] || fail "0.0" "GH_TOKEN env var not set"
git config --global credential.helper store
echo "https://x-access-token:${GH_TOKEN}@github.com" > ~/.git-credentials
export HF_HOME="${HF_HOME:-$WORKSPACE/hf-cache}"
mkdir -p "$HF_HOME/qwen2vl2b" "$HF_HOME/panns" "$WORKSPACE/raw_data"

# 0.1 — clone 9 repos at matrix tag
log "step 0.1 — clone 9 repos at $MATRIX_TAG"
for repo in "${REPOS[@]}"; do
  if [[ ! -d "$repo/.git" ]]; then
    git clone "$ORG/$repo.git" "$repo" || fail "0.1" "clone $repo"
    git -C "$repo" checkout "${REPO_TAGS[$repo]}" || fail "0.1" "checkout ${REPO_TAGS[$repo]} on $repo"
  fi
done
# pet-infra 切到 ecosystem-validation 分支
git -C pet-infra fetch origin feature/eco-validation-design-2026-04-25 || true
git -C pet-infra checkout feature/eco-validation-design-2026-04-25 || \
  log "  WARN: feature branch not on remote yet; staying on $MATRIX_TAG"

# 0.2 — conda + CUDA torch
log "step 0.2 — conda env + CUDA torch"
source "$(conda info --base)/etc/profile.d/conda.sh" 2>/dev/null || \
  fail "0.2" "conda not installed"
if ! conda env list | grep -q "^pet-pipeline "; then
  conda create -n pet-pipeline python=3.11 -y
fi
conda activate pet-pipeline
if ! python -c "import torch" 2>/dev/null; then
  pip install --quiet torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cu124 \
    || fail "0.2" "torch CUDA install failed"
fi
python -c "import torch; assert torch.cuda.is_available()" \
  || fail "0.2" "torch.cuda not available (check CUDA driver vs torch wheel)"
python -c "import torch; print(f'  torch {torch.__version__}, cuda {torch.version.cuda}')"

# 0.3 — pet-infra 3-step
log "step 0.3 — pet-infra setup (3-step)"
pip install --quiet "pet-schema @ git+$ORG/pet-schema.git@${REPO_TAGS[pet-schema]}" \
  || fail "0.3" "pet-schema install"
(cd pet-infra && pip install --quiet -e ".[dev,api,sync]") \
  || fail "0.3" "pet-infra install"
python -c "import pet_schema, pet_infra; print(f'  pet_schema={pet_schema.__version__} pet_infra={pet_infra.__version__}')" \
  || fail "0.3" "version assert"

# 0.4 — 7 仓 setup
log "step 0.4 — 7 downstream repos setup"
export PET_ALLOW_MISSING_SDK=1
for repo in pet-data pet-annotation pet-train pet-quantize pet-eval pet-ota pet-id; do
  log "  installing $repo..."
  (cd "$repo" && pip install --quiet -e ".[dev]") || fail "0.4" "$repo install"
done
python -c "
import pet_data, pet_annotation, pet_train, pet_eval, pet_quantize, pet_ota, pet_id
print('  all 7 import OK')
" || fail "0.4" "import check"

# 0.4.5 — DB init（FrameStore / AnnotationStore；非 Alembic）
log "step 0.4.5 — DB init"
python -c "
from pathlib import Path
from pet_data.storage.store import FrameStore
FrameStore(Path('$WORKSPACE/raw_data/frames.db'))
print('  frames.db init OK')
" || fail "0.4.5" "pet-data FrameStore init"
python -c "
from pet_annotation.store import AnnotationStore
s = AnnotationStore('$WORKSPACE/annotation.db')
s.init_schema()
print('  annotation.db init OK')
" || fail "0.4.5" "pet-annotation AnnotationStore init"

# 0.4.6 — API key 校验
log "step 0.4.6 — API key check"
[[ -n "${ANTHROPIC_API_KEY:-}" ]] || fail "0.4.6" "ANTHROPIC_API_KEY not set"
log "  ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:0:10}..."

# 0.4.7 — HF 模型预下载
log "step 0.4.7 — HF model preload"
if [[ ! -d "$HF_HOME/qwen2vl2b/model.safetensors" ]] && \
   [[ -z "$(ls -A "$HF_HOME/qwen2vl2b" 2>/dev/null)" ]]; then
  huggingface-cli download Qwen/Qwen2-VL-2B-Instruct \
    --local-dir "$HF_HOME/qwen2vl2b" --local-dir-use-symlinks False \
    || fail "0.4.7" "Qwen2-VL-2B download"
else
  log "  Qwen2-VL-2B already cached"
fi
PANNS_PATH="$HF_HOME/panns/MobileNetV2.pth"
if [[ ! -f "$PANNS_PATH" ]]; then
  curl -sL -o "$PANNS_PATH" \
    "https://zenodo.org/record/3987831/files/MobileNetV2_mAP%3D0.383.pth" \
    || fail "0.4.7" "PANNs MobileNetV2 download"
else
  log "  PANNs MobileNetV2 already cached"
fi

# 0.4.8 — auto-commit cron
log "step 0.4.8 — auto-commit cron"
CRON_LINE='*/15 * * * * cd '"$WORKSPACE"'/pet-infra && git diff --quiet docs/ecosystem-validation/ || (git add docs/ecosystem-validation/ && git commit -m "wip eco-validation" && git push) >> /tmp/eco-cron.log 2>&1'
( crontab -l 2>/dev/null | grep -v 'eco-validation' ; echo "$CRON_LINE" ) | crontab -
log "  cron installed"

# 0.5 — make test 全 9 仓
log "step 0.5 — make test on 9 repos"
for repo in "${REPOS[@]}"; do
  log "  testing $repo..."
  (cd "$repo" && make test 2>&1 | tail -20) || fail "0.5" "make test on $repo"
done

# 0.7 — no-wandb-residue（修：原版 set -e + || true 互锁）
log "step 0.7 — no-wandb-residue check on 5 repos"
for repo in pet-train pet-eval pet-quantize pet-ota pet-annotation; do
  residue=$(cd "$repo" && grep -rln "wandb" src/ tests/ 2>/dev/null | grep -vE 'no_wandb|wandb-residue|guard|test_no_wandb' || true)
  if [[ -n "$residue" ]]; then
    fail "0.7" "wandb residue in $repo: $residue"
  fi
done

# 0.8 — done
log "bootstrap COMPLETE — Phase 0 ready for execution"
