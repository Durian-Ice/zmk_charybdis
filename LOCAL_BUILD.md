# Local Firmware Build Guide

This directory contains a fast local build pipeline for compiling ZMK firmware directly on your machine without waiting for GitHub Actions.

---

## Prerequisites

- **Docker** running on your host machine (with permissions to run containers without `sudo` or configured via the Docker group).
- **Official Docker Image:** `zmkfirmware/zmk-build-arm:stable` (automatically pulled by Docker on first run).
- **Workspace:** By default, all dependencies (Zephyr SDK, modules, ZMK sources, and build cache) are placed into `./zmk-workspace` inside the current directory.

---

## Quick Start & First-Time Setup

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

### First-Time Initialization
When run for the first time, `./build.sh` detects that `zmk-workspace/` does not exist and interactively asks:

```text
[?] Workspace directory not found at: ./zmk-workspace
    This directory will contain Zephyr dependencies, ZMK sources, and the build cache (~2 GB).
    Create and initialize it now? [Y/n]
```

Pressing **Enter** or **`Y`** will automatically create the `./zmk-workspace` directory and pull all necessary dependencies via `west update`. (Pass `-y` or `--yes` to skip the prompt in automated environments).

All compiled `.uf2` binaries are written to the `dist/` directory:
- `dist/charybdis_qwerty_left.uf2`
- `dist/charybdis_qwerty_right.uf2`
- `dist/firmware_reset_nano_v2.uf2`

---

## Supplying Custom Directories & Dependencies

If you already have a local ZMK repository checkout, an existing Zephyr workspace, or custom driver modules elsewhere on your system, you can supply their paths via flags or environment variables:

### Command-Line Flags

| Flag / Option | Description | Default |
| :--- | :--- | :--- |
| `-w`, `--workspace-dir <path>` | Path for the Zephyr workspace & build cache | `./zmk-workspace` |
| `-z`, `--zmk-dir <path>` | Path to a local ZMK source checkout | `./zmk-workspace/zmk` |
| `-c`, `--config-dir <path>` | Path to the keyboard configuration repository | `.` (Current directory) |
| `-o`, `--output-dir <path>` | Destination folder for compiled `.uf2` files | `./dist` |
| `--pmw3610-dir <path>` | Path to a custom `zmk-pmw3610-driver` checkout | `./zmk-workspace/zmk-pmw3610-driver` |
| `--docker-image <tag>` | Docker image tag | `zmkfirmware/zmk-build-arm:stable` |
| `-y`, `--yes` | Automatically confirm workspace creation without prompting | `false` |

### Examples

```bash
# Build using an external ZMK source checkout
./build.sh --zmk-dir ~/repos/zmk right

# Specify a custom workspace location on another disk
./build.sh --workspace-dir /mnt/fast-ssd/zmk-workspace right

# Non-interactive first-time build
./build.sh -y left
```

### Environment Variables

All path overrides can also be passed via environment variables:

```bash
export ZMK_DIR=~/repos/zmk
export WORKSPACE_DIR=~/zmk-workspace
export OUTPUT_DIR=/tmp/firmware

./build.sh right
```

---

## Build Commands & Workflow Options

| Command / Flag | Description |
| :--- | :--- |
| `./build.sh [target]` | Build specific target(s): `left`, `right`, `reset`, `dongle`, `all`, or artifact name |
| `./build.sh -l`, `--list` | List all targets available in `build.yaml` |
| `./build.sh -p`, `--pristine` | Force a clean, pristine CMake reconfiguration before building |
| `./build.sh -k [layout]` | Override keymap layout (e.g. `-k colemak_dh` or `-k qwerty`) |
| `./build.sh --temp-env` | Build in an isolated temporary workspace directory and clean up upon exit |
| `./build.sh --shell` | Drop into an interactive container bash shell with Zephyr environment and `west` |
| `./build.sh --update` | Run `west update` inside the workspace to fetch updated dependencies |
| `./build.sh --clean` | Remove cached build directories in `zmk-workspace/build` |

---

## Fast Local Debugging Workflow

1. Edit C source, drivers, or headers in your ZMK tree (e.g. `app/src/ble.c` or sensor drivers).
2. Run `./build.sh right` (or `./build.sh left`).
3. Rebuilds are incremental and take **~1–2 seconds**.
4. Put the board into bootloader mode by **double-tapping the physical reset button** on the nice!nano.
5. Mount the `NICENANO` USB mass storage volume.
6. Copy the `.uf2` file from `dist/` to the `NICENANO` drive.

---

## Nix / NixOS Integration

A [`flake.nix`](flake.nix) is included for Nix users:

```bash
# Build firmware using Nix
nix run .#build -- right

# Enter development shell (includes Python + PyYAML, Docker, Git)
nix develop
```

---

## Workspace Layout

```
zmk-config/               # This configuration repository
├── build.sh              # Main build entrypoint wrapper
├── build.yaml            # Matrix definitions
├── config/               # Keymaps, layouts, and Kconfig flags
├── scripts/              # Build pipeline scripts
│   ├── build.py
│   ├── convert_keymap.py
│   └── check_split_status.py
├── dist/                 # Output directory for compiled .uf2 files
└── zmk-workspace/        # (Git-ignored) Zephyr dependencies, ZMK source, and build cache
    ├── .west/
    ├── zephyr/
    ├── modules/
    ├── zmk/
    └── build/
```
