# Local Firmware Build Guide

This directory contains a fast local build pipeline for compiling ZMK firmware directly on your machine without relying on GitHub Actions.

## Prerequisites

- **Docker** running on your host machine.
- The official Docker build image (`zmkfirmware/zmk-build-arm:stable`) is automatically used.
- Local ZMK source repository at `../zmk` (`/home/durian/personal/zmk`).

---

## Quick Start

From this directory (`zmk-config`):

```bash
# Build the right (central) half with ZMK Studio RPC snippet
./build.sh right

# Build the left (peripheral) half
./build.sh left

# Build the settings reset firmware
./build.sh reset

# Build all enabled targets from build.yaml
./build.sh
```

All compiled `.uf2` binaries are output to the `dist/` directory:
- `dist/charybdis_qwerty_left.uf2`
- `dist/charybdis_qwerty_right.uf2`
- `dist/firmware_reset_nano_v2.uf2`

---

## Fast Local Debugging Workflow

1. Edit C source or headers in `../zmk` (e.g. `zmk/app/src/ble.c`).
2. Run `./build.sh right` (or `left`).
3. Rebuilds are incremental and take **~1–2 seconds**.
4. Double-tap the reset button on your `nice_nano` to mount the mass storage drive.
5. Copy the corresponding `.uf2` from `dist/` onto the `NICENANO` volume.

---

## Command Reference & Options

| Command / Flag | Description |
|---|---|
| `./build.sh [target]` | Build specific target (`left`, `right`, `reset`, `dongle`, `all`) |
| `./build.sh -l` / `--list` | List all targets configured in `build.yaml` |
| `./build.sh -p` / `--pristine` | Force a clean pristine CMake reconfigure and build |
| `./build.sh --temp-env` | Build in an isolated temporary workspace directory and clean up on exit |
| `./build.sh -k [layout]` | Override keymap layout (`qwerty` or `colemak_dh`) |
| `./build.sh --shell` | Launch an interactive container shell with `west` and Zephyr SDK loaded |
| `./build.sh --clean` | Remove build caches from `../zmk-workspace/build` |
| `./build.sh --update` | Run `west update` to synchronize Zephyr/ZMK dependencies |

---

## Nix Flake Integration

If you use Nix / NixOS:

```bash
# Build using Nix
nix run .#build -- right

# Enter development shell (provides Python with PyYAML, Docker, Git)
nix develop
```

---

## Workspace Layout

```
personal/
├── zmk/                # ZMK firmware source code (active development / debug branch)
├── zmk-config/         # This repository (keymaps, shields, and build scripts)
│   ├── build.sh        # Main build entrypoint wrapper
│   ├── scripts/
│   │   ├── build.py    # Build orchestrator & staging generator
│   │   └── convert_keymap.py
│   └── dist/           # Generated .uf2 firmware binaries
└── zmk-workspace/      # Cached Zephyr modules and build artifacts
    ├── zephyr/
    ├── modules/
    └── build/
```
