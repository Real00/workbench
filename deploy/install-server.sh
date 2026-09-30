#!/usr/bin/env bash
# Workbench 服务器一键部署 / 升级（GHCR + 容器内自更新）
#
# 数据安全约定（脚本强制遵守）：
#   - 永不执行 docker compose down -v / volume rm / volume prune / system prune --volumes
#   - 自动沿用已有 Compose 项目名，使 mongo-data 等 named volume 继续挂载旧数据
#   - 默认只 recreate 需要变更的容器；mongo 镜像未变时通常不会动数据卷
#
# 用法：
#   A) 完整仓库：sudo ./deploy/install-server.sh
#   B) 精简部署目录（推荐）：把下列文件放在同一目录后执行 ./install-server.sh
#        compose.ghcr.yaml
#        install-server.sh          （本脚本，可放目录根）
#        .env                       （已有生产配置务必保留）
#   sudo INSTALL_DIR=/data/workbench ./install-server.sh
#   sudo COMPOSE_PROJECT_NAME=workbench ./install-server.sh
#
# 可选环境变量：
#   INSTALL_DIR          部署目录（默认：脚本所在目录，若其旁已有 compose/.env）
#   COMPOSE_PROJECT_NAME 强制使用的 compose 项目名（默认自动探测运行中的实例）
#   COMPOSE_FILE         默认 compose.ghcr.yaml
#   SKIP_LOGIN=1         跳过 docker login ghcr.io 提示
#   GHCR_IMAGE           默认 ghcr.io/real00/workbench:latest

set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-compose.ghcr.yaml}"
GHCR_IMAGE="${GHCR_IMAGE:-ghcr.io/real00/workbench:latest}"
SKIP_LOGIN="${SKIP_LOGIN:-0}"

log()  { printf '+ %s\n' "$*"; }
warn() { printf '! %s\n' "$*" >&2; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "缺少命令：$1"
}

# ---------- 定位素材目录 / 安装目录 ----------
# 支持两种布局：
#   1) 仓库：deploy/install-server.sh → 素材在仓库根（SCRIPT_DIR/..）
#   2) 扁平：/data/workbench/install-server.sh → 素材就在 SCRIPT_DIR
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

resolve_source_root() {
  local candidate
  for candidate in \
    "${SCRIPT_DIR}" \
    "$(cd "${SCRIPT_DIR}/.." && pwd)" \
    "${PWD}"; do
    if [[ -f "${candidate}/${COMPOSE_FILE}" ]]; then
      printf '%s' "${candidate}"
      return 0
    fi
  done
  return 1
}

if SOURCE_ROOT="$(resolve_source_root)"; then
  log "素材目录：${SOURCE_ROOT}"
else
  die "找不到 ${COMPOSE_FILE}。请放到脚本同目录，或在完整仓库根执行 ./deploy/install-server.sh
当前脚本目录：${SCRIPT_DIR}
需要至少：
  ${COMPOSE_FILE}
  .env（已有实例请用现成的，勿覆盖）"
fi

if [[ -n "${INSTALL_DIR:-}" ]]; then
  mkdir -p "${INSTALL_DIR}"
  INSTALL_DIR="$(cd "${INSTALL_DIR}" && pwd)"
elif [[ -f "${SOURCE_ROOT}/${COMPOSE_FILE}" || -f "${SOURCE_ROOT}/.env" ]]; then
  # 精简部署：素材已在目标目录时，就地安装，避免误写到 /opt/workbench
  INSTALL_DIR="${SOURCE_ROOT}"
elif [[ -f "${PWD}/${COMPOSE_FILE}" || -f "${PWD}/.env" ]]; then
  INSTALL_DIR="${PWD}"
else
  INSTALL_DIR="/opt/workbench"
  mkdir -p "${INSTALL_DIR}"
  INSTALL_DIR="$(cd "${INSTALL_DIR}" && pwd)"
fi

[[ "$(id -u)" -eq 0 ]] || die "请用 root 或 sudo 运行（需要访问 Docker / 部署目录）"

require_cmd docker
docker compose version >/dev/null 2>&1 || die "需要 Docker Compose v2（docker compose）"
require_cmd python3

# ---------- 安全护栏：禁止危险参数误用 ----------
assert_safe_compose_args() {
  local arg
  for arg in "$@"; do
    case "${arg}" in
      -v|--volumes|volume|prune)
        die "拒绝危险参数「${arg}」：本脚本不会删除 named volume（Mongo 数据）"
        ;;
    esac
  done
}

compose() {
  assert_safe_compose_args "$@"
  # shellcheck disable=SC2086
  docker compose -p "${PROJECT_NAME}" -f "${INSTALL_DIR}/${COMPOSE_FILE}" "$@"
}

# ---------- 探测已有实例（项目名 / mongo volume）----------
detect_running_project() {
  local id project
  # 优先：已在跑的 compose mongo 服务
  while read -r id; do
    [[ -z "${id}" ]] && continue
    project="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "${id}" 2>/dev/null || true)"
    if [[ -n "${project}" ]]; then
      printf '%s' "${project}"
      return 0
    fi
  done < <(docker ps --filter "label=com.docker.compose.service=mongo" --format '{{.ID}}')

  # 其次：挂着 */data/db 且镜像含 mongo 的容器
  while read -r id; do
    [[ -z "${id}" ]] && continue
    project="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "${id}" 2>/dev/null || true)"
    if [[ -n "${project}" ]]; then
      printf '%s' "${project}"
      return 0
    fi
  done < <(docker ps --filter "ancestor=mongo:8" --format '{{.ID}}')

  return 1
}

detect_mongo_volume() {
  local id vol
  while read -r id; do
    [[ -z "${id}" ]] && continue
    vol="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data/db"}}{{.Name}}{{end}}{{end}}' "${id}" 2>/dev/null || true)"
    if [[ -n "${vol}" ]]; then
      printf '%s' "${vol}"
      return 0
    fi
  done < <(docker ps -a --filter "label=com.docker.compose.service=mongo" --format '{{.ID}}')
  while read -r id; do
    [[ -z "${id}" ]] && continue
    vol="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data/db"}}{{.Name}}{{end}}{{end}}' "${id}" 2>/dev/null || true)"
    if [[ -n "${vol}" ]]; then
      printf '%s' "${vol}"
      return 0
    fi
  done < <(docker ps -a --filter "ancestor=mongo:8" --format '{{.ID}}')
  return 1
}

EXPECTED_MONGO_VOLUME=""
if [[ -n "${COMPOSE_PROJECT_NAME:-}" ]]; then
  PROJECT_NAME="${COMPOSE_PROJECT_NAME}"
  log "使用指定的 Compose 项目名：${PROJECT_NAME}"
else
  if DETECTED="$(detect_running_project 2>/dev/null || true)"; then
    if [[ -n "${DETECTED}" ]]; then
      PROJECT_NAME="${DETECTED}"
      log "探测到已有 Compose 项目：${PROJECT_NAME}（将沿用，避免新建空的 mongo volume）"
    else
      PROJECT_NAME="$(basename "${INSTALL_DIR}")"
      log "未探测到运行中的实例，使用目录名作为项目名：${PROJECT_NAME}"
    fi
  else
    PROJECT_NAME="$(basename "${INSTALL_DIR}")"
    log "未探测到运行中的实例，使用目录名作为项目名：${PROJECT_NAME}"
  fi
fi

if MONGO_VOL="$(detect_mongo_volume 2>/dev/null || true)"; then
  if [[ -n "${MONGO_VOL}" ]]; then
    EXPECTED_MONGO_VOLUME="${MONGO_VOL}"
    log "探测到现有 Mongo 数据卷：${EXPECTED_MONGO_VOLUME}"
    EXPECTED_BY_PROJECT="${PROJECT_NAME}_mongo-data"
    if [[ "${EXPECTED_MONGO_VOLUME}" != "${EXPECTED_BY_PROJECT}" ]]; then
      warn "现有卷名 ${EXPECTED_MONGO_VOLUME} 与项目默认 ${EXPECTED_BY_PROJECT} 不一致。"
      warn "若继续 up 可能挂上新的空卷。请设置 COMPOSE_PROJECT_NAME 使「项目名_mongo-data」等于现有卷名后重试。"
      die "已中止，避免误挂空 Mongo 卷"
    fi
  fi
fi

# ---------- 同步部署文件（不覆盖已有 .env）----------
log "部署目录：${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"

copy_file() {
  local src="$1" dest="$2" mode="${3:-0644}"
  [[ -f "${src}" ]] || die "缺少文件：${src}"
  if [[ "$(cd "$(dirname "${src}")" && pwd)/$(basename "${src}")" == \
        "$(cd "$(dirname "${dest}")" 2>/dev/null && pwd)/$(basename "${dest}")" ]]; then
    log "已就位：${dest}"
    chmod "${mode}" "${dest}" 2>/dev/null || true
    return 0
  fi
  install -m "${mode}" "${src}" "${dest}"
  log "已同步：${dest}"
}

copy_file "${SOURCE_ROOT}/${COMPOSE_FILE}" "${INSTALL_DIR}/${COMPOSE_FILE}"

if [[ ! -f "${INSTALL_DIR}/.env" ]]; then
  if [[ -f "${SOURCE_ROOT}/.env" && "${SOURCE_ROOT}/.env" != "${INSTALL_DIR}/.env" ]]; then
    log "复制 .env → ${INSTALL_DIR}/.env"
    install -m 0600 "${SOURCE_ROOT}/.env" "${INSTALL_DIR}/.env"
  elif [[ -f "${SOURCE_ROOT}/.env.example" ]]; then
    warn "未找到 .env，从 .env.example 生成（请务必改掉默认密码与密钥）"
    install -m 0600 "${SOURCE_ROOT}/.env.example" "${INSTALL_DIR}/.env"
  else
    die "需要 ${INSTALL_DIR}/.env（沿用现有生产 .env，勿用空模板覆盖）"
  fi
else
  log "保留已有 .env（不覆盖）"
fi

# 一次性迁移：停用旧宿主机更新服务，避免它继续消费历史请求。
if command -v systemctl >/dev/null 2>&1 && \
   systemctl cat workbench-update-agent.service >/dev/null 2>&1; then
  systemctl disable --now workbench-update-agent.service
  log "已停用旧更新服务，后续由容器内启动器管理更新"
fi
python3 - "${INSTALL_DIR}/.env" <<'PYENV'
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
obsolete = {"WORKBENCH_UPDATE_AGENT_TOKEN", "WORKBENCH_UPDATE_CONTROL_DIR", "WORKBENCH_UPDATE_GITHUB_REF"}
lines = path.read_text().splitlines()
path.write_text("\n".join(line for line in lines if line.lstrip("# ").split("=", 1)[0] not in obsolete) + "\n")
PYENV

# 写入 compose 项目名，后续手动 docker compose 也一致
if ! grep -qE '^COMPOSE_PROJECT_NAME=' "${INSTALL_DIR}/.env" 2>/dev/null; then
  printf '\nCOMPOSE_PROJECT_NAME=%s\n' "${PROJECT_NAME}" >>"${INSTALL_DIR}/.env"
  log "已写入 COMPOSE_PROJECT_NAME=${PROJECT_NAME}"
fi

# ---------- GHCR 登录提示 ----------
if [[ "${SKIP_LOGIN}" != "1" ]]; then
  if ! docker pull --quiet "${GHCR_IMAGE}" >/dev/null 2>&1; then
    warn "无法拉取 ${GHCR_IMAGE}。"
    warn "若包为私有，请先：docker login ghcr.io"
    warn "登录后再重新运行本脚本；或设置 SKIP_LOGIN=1 跳过预检（up 时仍会 pull）。"
    die "镜像拉取预检失败"
  fi
  log "镜像可拉取：${GHCR_IMAGE}"
fi

# ---------- 拉起 / 升级（绝不 -v）----------
cd "${INSTALL_DIR}"
export COMPOSE_PROJECT_NAME="${PROJECT_NAME}"

log "拉取镜像…"
compose pull

log "启动/更新服务（保留 named volume；不用 down -v）…"
compose up -d

# 再次确认 mongo 挂载的是预期卷
MONGO_CID="$(docker ps --filter "label=com.docker.compose.project=${PROJECT_NAME}" --filter "label=com.docker.compose.service=mongo" --format '{{.ID}}' | head -n1 || true)"
if [[ -n "${MONGO_CID}" ]]; then
  ACTIVE_VOL="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data/db"}}{{.Name}}{{end}}{{end}}' "${MONGO_CID}")"
  log "当前 Mongo 容器数据卷：${ACTIVE_VOL}"
  if [[ -n "${EXPECTED_MONGO_VOLUME}" && "${ACTIVE_VOL}" != "${EXPECTED_MONGO_VOLUME}" ]]; then
    die "Mongo 数据卷已变化（${EXPECTED_MONGO_VOLUME} → ${ACTIVE_VOL}）。请立即检查，勿执行 volume 删除。"
  fi
fi

PORT="$(grep -E '^WORKBENCH_PORT=' "${INSTALL_DIR}/.env" 2>/dev/null | head -n1 | cut -d= -f2- || true)"
PORT="${PORT:-8080}"

cat <<EOF

部署完成。
  目录:     ${INSTALL_DIR}
  项目名:   ${PROJECT_NAME}
  Compose:  ${COMPOSE_FILE}
  访问:     http://<服务器IP>:${PORT}
  Mongo 卷: ${EXPECTED_MONGO_VOLUME:-${PROJECT_NAME}_mongo-data}（未删除、未 prune）

设置页 →「版本更新」可检查并一键更新。
基础镜像升级（同样不删卷）：
  cd ${INSTALL_DIR} && COMPOSE_PROJECT_NAME=${PROJECT_NAME} docker compose -f ${COMPOSE_FILE} pull app && \\
    COMPOSE_PROJECT_NAME=${PROJECT_NAME} docker compose -f ${COMPOSE_FILE} up -d app

EOF
