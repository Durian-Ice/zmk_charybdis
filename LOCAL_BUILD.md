# Local Firmware Build Guide

This directory contains a fast local build pipeline for compiling ZMK firmware directly on your machine without waiting for GitHub Actions.

---

## Prerequisites

- **Docker** running on your host machine (with permission to run containers without `sudo` or configured via Docker group).
- **Official Docker Image:** `zmkfirmware/zmk-build-arm:stable` (automatically downloaded by Docker on first run).
- **Local ZMK Repository:** `../zmk` (`/home/durian/personal/zmk`).

---

## Quick Start

Run `./build.sh` from this directory:

```bash
# Build the right (central) half
./build.sh right

# Build the left (peripheral) half
./build.sh left

# Build the settings reset firmware
./build.sh reset

# Build all enabled targets defined in build.yaml
./build.sh
```

All compiled `.uf2` binaries are written to the `dist/` directory:
- `dist/charybdis_qwerty_left.uf2`
- `dist/charybdis_qwerty_right.uf2`
- `dist/firmware_reset_nano_v2.uf2`

---

## How `build.sh` Works

`./build.sh` is a thin, high-performance wrapper around [scripts/build.py](file:///home/durian/personal/zmk-config/scripts/build.py) that executes inside the Zephyr Docker container:

1. **Matrix Parsing:** Reads build combinations directly from [build.yaml](file:///home/durian/personal/zmk-config/build.yaml).
2. **Keymap Conversion:** Runs [scripts/convert_keymap.py](file:///home/durian/personal/zmk-config/scripts/convert_keymap.py) to sync keymaps only if changed.
3. **Staging & Module Assembly:** Assembles the shield definition, `charybdis-layouts.dtsi`, and the [badjeff/zmk-pmw3610-driver](https://github.com/badjeff/zmk-pmw3610-driver) module into a stage directory.
4. **Fast Incremental Builds:** If the build directory already exists, it invokes Ninja directly for **~1–2s instant rebuilds**. If files changed or `-p` is passed, it triggers `west build`.
5. **Artifact Collection:** Extracts and copies the generated `zmk.uf2` to `dist/`.

---

## Command-Line Options & Flags

| Command / Flag | Description |
| :--- | :--- |
| `./build.sh [target]` | Build specific target(s): `left`, `right`, `reset`, `dongle`, `all`, or artifact name |
| `./build.sh -l`, `--list` | List all targets available in `build.yaml` |
| `./build.sh -p`, `--pristine` | Force a clean, pristine CMake reconfiguration before building |
| `./build.sh -k [layout]` | Override keymap layout (e.g. `-k colemak_dh` or `-k qwerty`) |
| `./build.sh --temp-env` | Build in an isolated temporary workspace directory and clean up upon exit |
| `./build.sh --shell` | Drop into an interactive container bash shell with Zephyr environment and `west` |
| `./build.sh --update` | Run `west update` inside the workspace to fetch updated Zephyr dependencies |
| `./build.sh --clean` | Remove cached build directories in `../zmk-workspace/build` |

---

## Environment Variables

You can customize directory paths via environment variables:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `ZMK_DIR` | `../zmk` | Path to ZMK source tree |
| `WORKSPACE_DIR` | `../zmk-workspace` | Path to west workspace (Zephyr modules & build cache) |
| `CONFIG_DIR` | Current directory | Path to `zmk-config` repository |
| `OUTPUT_DIR` | `dist/` | Destination folder for compiled `.uf2` files |
| `DOCKER_IMAGE` | `zmkfirmware/zmk-build-arm:stable` | Build container image |

Example:
```bash
OUTPUT_DIR=/tmp/firmware ZMK_DIR=~/projects/zmk ./build.sh right
```

---

## Fast Local Debugging Workflow

1. Edit C source, drivers, or headers in `../zmk` (e.g. `app/src/ble.c` or sensor drivers).
2. Run `./build.sh right` (or `./build.sh left`).
3. Rebuilds are incremental and take **~1–2 seconds**.
4. Put the board into bootloader mode by **double-tapping the physical reset button** on the nice!nano.
5. Mount the `NICENANO` USB mass storage volume.
6. Copy the `.uf2` file from `dist/` to the `NICENANO` drive.

---

## Nix / NixOS Integration

A [flake.nix](file:///home/durian/personal/zmk-config/flake.nix) is included for Nix users:

```bash
# Build firmware using Nix
nix run .#build -- right

# Enter development shell (includes Python + PyYAML, Docker, Git)
nix develop
```

---

## Workspace Layout

```
personal/
├── zmk/                # ZMK firmware source code (local checkout)
├── zmk-config/         # This config repo (keymaps, shields, build scripts)
│   ├── build.sh        # Main build entrypoint wrapper
│   ├── scripts/
│   │   ├── build.py    # Build orchestrator & staging pipeline
│   │   ├── convert_keymap.py
│   │   └── check_split_status.py
│   └── dist/           # Output directory for compiled .uf2 files
└── zmk-workspace/      # Cached Zephyr dependencies & build cache
    ├── zephyr/
    ├── modules/
    └── build/
```
