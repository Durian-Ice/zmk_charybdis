#!/usr/bin/env bash
set -e

# Base directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Overridable paths via environment variables or CLI flags
CONFIG_DIR="${CONFIG_DIR:-${SCRIPT_DIR}}"
WORKSPACE_DIR="${WORKSPACE_DIR:-${CONFIG_DIR}/zmk-workspace}"
OUTPUT_DIR="${OUTPUT_DIR:-${CONFIG_DIR}/dist}"
ZMK_DIR="${ZMK_DIR:-}"
PMW3610_DIR="${PMW3610_DIR:-}"
DOCKER_IMAGE="${DOCKER_IMAGE:-zmkfirmware/zmk-build-arm:stable}"

# Flags
TEMP_ENV=false
ASSUME_YES=false
PASSTHROUGH_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace-dir|-w)
      WORKSPACE_DIR="$(realpath -m "$2")"
      shift 2
      ;;
    --zmk-dir|-z)
      ZMK_DIR="$(realpath -m "$2")"
      shift 2
      ;;
    --config-dir|-c)
      CONFIG_DIR="$(realpath -m "$2")"
      shift 2
      ;;
    --output-dir|-o)
      OUTPUT_DIR="$(realpath -m "$2")"
      shift 2
      ;;
    --pmw3610-dir)
      PMW3610_DIR="$(realpath -m "$2")"
      shift 2
      ;;
    --docker-image)
      DOCKER_IMAGE="$2"
      shift 2
      ;;
    -y|--yes)
      ASSUME_YES=true
      shift
      ;;
    --temp-env|--temp-workspace)
      TEMP_ENV=true
      shift
      ;;
    *)
      PASSTHROUGH_ARGS+=("$1")
      shift
      ;;
  esac
done

# Check if workspace directory exists; prompt user if running interactively
if [ ! -d "${WORKSPACE_DIR}" ] && [ "${TEMP_ENV}" != "true" ]; then
  if [ "${ASSUME_YES}" = false ] && [ -t 0 ]; then
    echo -e "\033[1;33m[?] Workspace directory not found at: ${WORKSPACE_DIR}\033[0m"
    echo -e "    This directory will contain Zephyr dependencies, ZMK sources, and the build cache (~2 GB)."
    read -r -p "    Create and initialize it now? [Y/n] " response
    case "$response" in
      [nN][oO]|[nN])
        echo -e "\033[1;31mBuild aborted.\033[0m"
        echo "You can specify an existing workspace using --workspace-dir <path>"
        echo "or an external ZMK source repository using --zmk-dir <path>."
        exit 0
        ;;
      *)
        echo -e "\033[1;32m==> Creating workspace directory: ${WORKSPACE_DIR}...\033[0m"
        mkdir -p "${WORKSPACE_DIR}"
        ;;
    esac
  else
    mkdir -p "${WORKSPACE_DIR}"
  fi
fi

TEMP_DIR=""
cleanup() {
  if [ -n "${TEMP_DIR}" ] && [ -d "${TEMP_DIR}" ]; then
    echo -e "\033[1;33mCleaning up temporary environment at ${TEMP_DIR}...\033[0m"
    rm -rf "${TEMP_DIR}"
  fi
}

if [ "${TEMP_ENV}" = true ]; then
  TEMP_DIR="$(mktemp -d "${CONFIG_DIR}/.tmp-workspace-XXXXXXXXXX")"
  trap cleanup EXIT
  WORKSPACE_DIR="${TEMP_DIR}"
  echo -e "\033[1;34m==> Using isolated temporary workspace: ${WORKSPACE_DIR}\033[0m"
fi

# Ensure workspace and output directories exist
mkdir -p "${WORKSPACE_DIR}"
mkdir -p "${OUTPUT_DIR}"

CONTAINER_WORKSPACE="/app/workspace"
CONTAINER_CONFIG="/app/config"
CONTAINER_OUTPUT="/app/dist"

DOCKER_MOUNTS=(
  -v "${WORKSPACE_DIR}:${CONTAINER_WORKSPACE}"
  -v "${CONFIG_DIR}:${CONTAINER_CONFIG}"
  -v "${OUTPUT_DIR}:${CONTAINER_OUTPUT}"
)

# Resolve ZMK container location
if [ -n "${ZMK_DIR}" ] && [ -d "${ZMK_DIR}" ]; then
  if [[ "${ZMK_DIR}" == "${WORKSPACE_DIR}"* ]]; then
    REL_ZMK="$(realpath --relative-to="${WORKSPACE_DIR}" "${ZMK_DIR}")"
    CONTAINER_ZMK="${CONTAINER_WORKSPACE}/${REL_ZMK}"
  elif [[ "${ZMK_DIR}" == "${CONFIG_DIR}"* ]]; then
    REL_ZMK="$(realpath --relative-to="${CONFIG_DIR}" "${ZMK_DIR}")"
    CONTAINER_ZMK="${CONTAINER_CONFIG}/${REL_ZMK}"
  else
    CONTAINER_ZMK="/app/zmk"
    DOCKER_MOUNTS+=(-v "${ZMK_DIR}:${CONTAINER_ZMK}")
  fi
else
  CONTAINER_ZMK="${CONTAINER_WORKSPACE}/zmk"
fi

# Resolve PMW3610 driver container location if custom path supplied
if [ -n "${PMW3610_DIR}" ] && [ -d "${PMW3610_DIR}" ]; then
  if [[ "${PMW3610_DIR}" == "${WORKSPACE_DIR}"* ]]; then
    REL_PMW="$(realpath --relative-to="${WORKSPACE_DIR}" "${PMW3610_DIR}")"
    CONTAINER_PMW="${CONTAINER_WORKSPACE}/${REL_PMW}"
  elif [[ "${PMW3610_DIR}" == "${CONFIG_DIR}"* ]]; then
    REL_PMW="$(realpath --relative-to="${CONFIG_DIR}" "${PMW3610_DIR}")"
    CONTAINER_PMW="${CONTAINER_CONFIG}/${REL_PMW}"
  else
    CONTAINER_PMW="/app/modules/zmk-pmw3610-driver"
    DOCKER_MOUNTS+=(-v "${PMW3610_DIR}:${CONTAINER_PMW}")
  fi
  PASSTHROUGH_ARGS+=("--pmw3610-dir" "${CONTAINER_PMW}")
fi

# If temporary workspace, link cached zephyr, modules, and west configuration
if [ "${TEMP_ENV}" = true ]; then
  BASE_WORKSPACE="${CONFIG_DIR}/zmk-workspace"
  if [ -d "${BASE_WORKSPACE}/zephyr" ]; then
    echo -e "Linking cached zephyr and modules from ${BASE_WORKSPACE}..."
    ln -s "${CONTAINER_WORKSPACE}/zephyr" "${CONTAINER_WORKSPACE}/zephyr" 2>/dev/null || true
  fi
fi

# Check for interactive shell request
if [ "${PASSTHROUGH_ARGS[0]}" == "--shell" ] || [ "${PASSTHROUGH_ARGS[0]}" == "shell" ]; then
  echo -e "\033[1;32mStarting interactive ZMK build shell...\033[0m"
  echo -e "Environment loaded with west, Zephyr SDK, and Python."
  echo -e "Workspace: ${CONTAINER_WORKSPACE} | Config: ${CONTAINER_CONFIG}\n"
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
