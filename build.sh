#!/usr/bin/env bash
set -e

# Base directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PERSONAL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Overridable paths via environment variables or CLI flags
ZMK_DIR="${ZMK_DIR:-${PERSONAL_DIR}/zmk}"
WORKSPACE_DIR="${WORKSPACE_DIR:-${PERSONAL_DIR}/zmk-workspace}"
CONFIG_DIR="${CONFIG_DIR:-${SCRIPT_DIR}}"
OUTPUT_DIR="${OUTPUT_DIR:-${SCRIPT_DIR}/dist}"
DOCKER_IMAGE="${DOCKER_IMAGE:-zmkfirmware/zmk-build-arm:stable}"

# Parse temp env flags
TEMP_ENV=false
PASSTHROUGH_ARGS=()

for arg in "$@"; do
  case "$arg" in
    --temp-env|--temp-workspace)
      TEMP_ENV=true
      ;;
    *)
      PASSTHROUGH_ARGS+=("$arg")
      ;;
  esac
done

# Check if ZMK directory exists
if [ ! -d "${ZMK_DIR}" ]; then
  echo -e "\033[1;31mError: ZMK source repository not found at ${ZMK_DIR}\033[0m"
  exit 1
fi

TEMP_DIR=""
cleanup() {
  if [ -n "${TEMP_DIR}" ] && [ -d "${TEMP_DIR}" ]; then
    echo -e "\033[1;33mCleaning up temporary environment at ${TEMP_DIR}...\033[0m"
    rm -rf "${TEMP_DIR}"
  fi
}

if [ "${TEMP_ENV}" = true ]; then
  TEMP_DIR="$(mktemp -d "${PERSONAL_DIR}/.tmp-workspace-XXXXXXXXXX")"
  trap cleanup EXIT
  WORKSPACE_DIR="${TEMP_DIR}"
  echo -e "\033[1;34m==> Using isolated temporary workspace: ${WORKSPACE_DIR}\033[0m"
fi

# Ensure workspace and output directories exist
mkdir -p "${WORKSPACE_DIR}"
mkdir -p "${OUTPUT_DIR}"

DOCKER_MOUNTS=(
  -v "${PERSONAL_DIR}:/personal"
)

# Resolve container path for CONFIG
if [[ "${CONFIG_DIR}" != "${PERSONAL_DIR}"* ]]; then
  DOCKER_MOUNTS+=(-v "${CONFIG_DIR}:${CONFIG_DIR}")
  CONTAINER_CONFIG="${CONFIG_DIR}"
else
  REL_CFG="$(realpath --relative-to="${PERSONAL_DIR}" "${CONFIG_DIR}")"
  CONTAINER_CONFIG="/personal/${REL_CFG}"
fi

# Resolve container path for ZMK
if [[ "${ZMK_DIR}" != "${PERSONAL_DIR}"* ]]; then
  DOCKER_MOUNTS+=(-v "${ZMK_DIR}:${ZMK_DIR}")
  CONTAINER_ZMK="${ZMK_DIR}"
else
  REL_ZMK="$(realpath --relative-to="${PERSONAL_DIR}" "${ZMK_DIR}")"
  CONTAINER_ZMK="/personal/${REL_ZMK}"
fi

# Resolve container path for OUTPUT
if [[ "${OUTPUT_DIR}" != "${PERSONAL_DIR}"* ]]; then
  DOCKER_MOUNTS+=(-v "${OUTPUT_DIR}:${OUTPUT_DIR}")
  CONTAINER_OUTPUT="${OUTPUT_DIR}"
else
  REL_OUT="$(realpath --relative-to="${PERSONAL_DIR}" "${OUTPUT_DIR}")"
  CONTAINER_OUTPUT="/personal/${REL_OUT}"
fi

# Resolve container path for WORKSPACE
if [[ "${WORKSPACE_DIR}" != "${PERSONAL_DIR}"* ]]; then
  DOCKER_MOUNTS+=(-v "${WORKSPACE_DIR}:${WORKSPACE_DIR}")
  CONTAINER_WORKSPACE="${WORKSPACE_DIR}"
else
  REL_WS="$(realpath --relative-to="${PERSONAL_DIR}" "${WORKSPACE_DIR}")"
  CONTAINER_WORKSPACE="/personal/${REL_WS}"
fi

# If temporary workspace, link cached zephyr, modules, and west configuration
if [ "${TEMP_ENV}" = true ]; then
  BASE_WORKSPACE="${PERSONAL_DIR}/zmk-workspace"
  if [ -d "${BASE_WORKSPACE}/zephyr" ]; then
    echo -e "Linking cached zephyr and modules from ${BASE_WORKSPACE}..."
    ln -s "/personal/zmk-workspace/zephyr" "${WORKSPACE_DIR}/zephyr"
    [ -d "${BASE_WORKSPACE}/modules" ] && ln -s "/personal/zmk-workspace/modules" "${WORKSPACE_DIR}/modules"
    [ -d "${BASE_WORKSPACE}/zmk-pmw3610-driver" ] && ln -s "/personal/zmk-workspace/zmk-pmw3610-driver" "${WORKSPACE_DIR}/zmk-pmw3610-driver"
    [ -d "${BASE_WORKSPACE}/.west" ] && cp -r "${BASE_WORKSPACE}/.west" "${WORKSPACE_DIR}/.west"
    ln -s "${CONTAINER_CONFIG}" "${WORKSPACE_DIR}/zmk-config"
    ln -s "${CONTAINER_ZMK}" "${WORKSPACE_DIR}/zmk"
  fi
fi

# Check for interactive shell request
if [ "${PASSTHROUGH_ARGS[0]}" == "--shell" ] || [ "${PASSTHROUGH_ARGS[0]}" == "shell" ]; then
  echo -e "\033[1;32mStarting interactive ZMK build shell...\033[0m"
  echo -e "Environment loaded with west, Zephyr SDK, and Python."
  echo -e "Workspace: ${CONTAINER_WORKSPACE} | ZMK: ${CONTAINER_ZMK} | Config: ${CONTAINER_CONFIG}\n"
  exec docker run --rm -it \
    -u "$(id -u):$(id -g)" \
    -e ZEPHYR_BASE="${CONTAINER_WORKSPACE}/zephyr" \
    -e CMAKE_PREFIX_PATH="${CONTAINER_WORKSPACE}/zephyr/share/zephyr-package/cmake" \
    "${DOCKER_MOUNTS[@]}" \
    -w "${CONTAINER_WORKSPACE}" \
    "${DOCKER_IMAGE}" \
    bash -c "git config --global --add safe.directory '*' 2>/dev/null || true; exec bash"
fi

# Run build script inside container
docker run --rm \
  -u "$(id -u):$(id -g)" \
  -e ZEPHYR_BASE="${CONTAINER_WORKSPACE}/zephyr" \
  -e CMAKE_PREFIX_PATH="${CONTAINER_WORKSPACE}/zephyr/share/zephyr-package/cmake" \
  "${DOCKER_MOUNTS[@]}" \
  -w "${CONTAINER_WORKSPACE}" \
  "${DOCKER_IMAGE}" \
  bash -c "git config --global --add safe.directory '*' 2>/dev/null || true; python3 ${CONTAINER_CONFIG}/scripts/build.py --workspace-dir ${CONTAINER_WORKSPACE} --zmk-dir ${CONTAINER_ZMK} --config-dir ${CONTAINER_CONFIG} --output-dir ${CONTAINER_OUTPUT} ${PASSTHROUGH_ARGS[*]}"
