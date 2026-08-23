#!/usr/bin/env python3
import argparse
import filecmp
import os
import shutil
import subprocess
import sys
import yaml

DEFAULT_ZMK_DIR = "/personal/zmk"
DEFAULT_CONFIG_DIR = "/personal/zmk-config"
DEFAULT_WORKSPACE_DIR = "/personal/zmk-workspace"
DEFAULT_OUTPUT_DIR = "/personal/zmk-config/dist"


def run_cmd(cmd, cwd=None, env=None, check=True):
    print(f"\033[1;34m==>\033[0m \033[1m{' '.join(cmd) if isinstance(cmd, list) else cmd}\033[0m")
    res = subprocess.run(cmd, cwd=cwd, env=env, shell=isinstance(cmd, str))
    if check and res.returncode != 0:
        print(f"\033[1;31mCommand failed with exit code {res.returncode}\033[0m")
        sys.exit(res.returncode)
    return res


def copy_if_different(src, dst):
    if not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        return True
    if not filecmp.cmp(src, dst, shallow=False):
        shutil.copy2(src, dst)
        return True
    return False


def write_if_different(dst, content):
    if os.path.exists(dst):
        with open(dst, "r") as f:
            if f.read() == content:
                return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w") as f:
        f.write(content)
    return True


def sync_dir(src, dst):
    os.makedirs(dst, exist_ok=True)
    for root, _, files in os.walk(src):
        rel_path = os.path.relpath(root, src)
        dest_root = os.path.join(dst, rel_path)
        os.makedirs(dest_root, exist_ok=True)
        for f in files:
            s = os.path.join(root, f)
            d = os.path.join(dest_root, f)
            copy_if_different(s, d)


def convert_keymaps(config_dir):
    script_path = os.path.join(config_dir, "scripts", "convert_keymap.py")
    keymap_path = os.path.join(config_dir, "config", "charybdis.keymap")
    if os.path.exists(script_path) and os.path.exists(keymap_path):
        run_cmd([sys.executable, script_path, "-c", "q2c", "--in-path", keymap_path])


def load_build_matrix(config_dir):
    build_yaml_path = os.path.join(config_dir, "build.yaml")
    if not os.path.exists(build_yaml_path):
        print(f"Error: {build_yaml_path} not found")
        sys.exit(1)
    with open(build_yaml_path, "r") as f:
        data = yaml.safe_load(f)
    return data.get("include", []) if data else []


def prepare_staging(target, config_dir, workspace_dir, stage_dir):
    os.makedirs(os.path.join(stage_dir, "config"), exist_ok=True)
    os.makedirs(os.path.join(stage_dir, "boards", "shields", "charybdis"), exist_ok=True)

    # 1. Sync config files without updating mtimes if unchanged
    src_config = os.path.join(config_dir, "config")
    sync_dir(src_config, os.path.join(stage_dir, "config"))

    # Also make sure qwerty.keymap exists
    qwerty_source = os.path.join(config_dir, "config", "charybdis.keymap")
    dest_qwerty = os.path.join(stage_dir, "config", "qwerty.keymap")
    if os.path.exists(qwerty_source):
        copy_if_different(qwerty_source, dest_qwerty)

    shield = target.get("shield", "")
    fmt = target.get("format", "bt")
    keymap = target.get("keymap", "qwerty")

    # 2. Keymap setup
    if shield != "settings_reset":
        keymap_file = os.path.join(stage_dir, "config", f"{keymap}.keymap")
        if not os.path.exists(keymap_file):
            keymap_file = os.path.join(stage_dir, "config", "charybdis.keymap")
        
        target_keymap = os.path.join(stage_dir, "config", "charybdis.keymap")
        with open(keymap_file, "r") as f:
            content = f.read()

        if "bt" in fmt:
            content = content.replace("device = <&trackball_split>;", "device = <&trackball>;")

        write_if_different(target_keymap, content)

    # 3. Shield files setup
    if shield != "settings_reset":
        shield_folder = "charybdis-dongle" if fmt == "dongle" else "charybdis-bt"
        src_shield = os.path.join(config_dir, "boards", "shields", shield_folder)
        dest_shield = os.path.join(stage_dir, "boards", "shields", "charybdis")

        if os.path.exists(src_shield):
            sync_dir(src_shield, dest_shield)

        # Copy physical layout file
        layouts_src = os.path.join(config_dir, "config", "charybdis-layouts.dtsi")
        if os.path.exists(layouts_src):
            copy_if_different(layouts_src, os.path.join(dest_shield, "charybdis-layouts.dtsi"))

        # Copy zephyr/ module descriptor
        zephyr_mod = os.path.join(config_dir, "zephyr")
        if os.path.exists(zephyr_mod):
            sync_dir(zephyr_mod, os.path.join(stage_dir, "zephyr"))


def build_target(target, args, config_dir, zmk_dir, workspace_dir, output_dir):
    board = target.get("board", "nice_nano//zmk")
    shield = target.get("shield", "")
    snippet = target.get("snippet", "")
    fmt = target.get("format", "bt")
    keymap = target.get("keymap", "qwerty")
    cmake_args = target.get("cmake-args", "")
    artifact_name = target.get("artifact-name", f"{shield}-{board}" if shield else f"{board}")

    print("\n" + "=" * 70)
    print(f"\033[1;32mBuilding Target: {artifact_name}\033[0m")
    print(f"  Board:   {board}")
    print(f"  Shield:  {shield or '(none)'}")
    print(f"  Format:  {fmt}")
    print(f"  Keymap:  {keymap}")
    if snippet:
        print(f"  Snippet: {snippet}")
    print("=" * 70)

    target_slug = artifact_name.replace("-", "_").replace(" ", "_")
    stage_dir = os.path.join(workspace_dir, "build", f"stage_{target_slug}")
    build_dir = os.path.join(workspace_dir, "build", f"target_{target_slug}")

    prepare_staging(target, config_dir, workspace_dir, stage_dir)

    extra_west = []
    if args.pristine:
        extra_west.append("-p")
    if snippet:
        extra_west.extend(["-S", snippet])

    extra_cmake = [
        f"-DZMK_CONFIG={stage_dir}/config",
    ]
    if shield:
        extra_cmake.append(f"-DSHIELD={shield}")

    if shield != "settings_reset":
        pmw_driver = os.path.join(workspace_dir, "zmk-pmw3610-driver")
        modules = [stage_dir]
        if os.path.exists(pmw_driver):
            modules.append(pmw_driver)
        extra_cmake.append(f"-DZMK_EXTRA_MODULES={';'.join(modules)}")

    if cmake_args:
        extra_cmake.extend(cmake_args.split())

    env = os.environ.copy()
    env["ZEPHYR_BASE"] = os.path.join(workspace_dir, "zephyr")
    env["CMAKE_PREFIX_PATH"] = os.path.join(workspace_dir, "zephyr", "share", "zephyr-package", "cmake")

    # Fast incremental path: if ninja cache exists and not pristine, try building directly
    built = False
    if not args.pristine and os.path.exists(os.path.join(build_dir, "build.ninja")):
        fast_res = run_cmd(["west", "build", "-d", build_dir], cwd=workspace_dir, env=env, check=False)
        if fast_res.returncode == 0:
            built = True

    if not built:
        cmd = [
            "west", "build",
            "-s", os.path.join(zmk_dir, "app"),
            "-d", build_dir,
            "-b", board,
        ] + extra_west + ["--"] + extra_cmake
        run_cmd(cmd, cwd=workspace_dir, env=env)

    # Collect artifacts
    os.makedirs(output_dir, exist_ok=True)
    uf2_file = os.path.join(build_dir, "zephyr", "zmk.uf2")
    bin_file = os.path.join(build_dir, "zephyr", "zmk.bin")

    dest_file = None
    if os.path.exists(uf2_file):
        dest_file = os.path.join(output_dir, f"{artifact_name}.uf2")
        shutil.copy2(uf2_file, dest_file)
    elif os.path.exists(bin_file):
        dest_file = os.path.join(output_dir, f"{artifact_name}.bin")
        shutil.copy2(bin_file, dest_file)

    if dest_file:
        size = os.path.getsize(dest_file)
        print(f"\033[1;32m✓ Output generated:\033[0m {dest_file} ({size:,} bytes)")
    else:
        print(f"\033[1;31mWarning: No .uf2 or .bin output found in {build_dir}/zephyr\033[0m")

    return dest_file


def main():
    parser = argparse.ArgumentParser(description="ZMK Local Build Pipeline")
    parser.add_argument("targets", nargs="*", help="Targets to build (left, right, reset, dongle, all, or specific artifact name)")
    parser.add_argument("-p", "--pristine", action="store_true", help="Perform a pristine clean build")
    parser.add_argument("-l", "--list", action="store_true", help="List available targets in build.yaml")
    parser.add_argument("--clean", action="store_true", help="Clean build directories")
    parser.add_argument("--update", action="store_true", help="Run west update")
    parser.add_argument("--zmk-dir", default=DEFAULT_ZMK_DIR, help="Path to ZMK repo")
    parser.add_argument("--config-dir", default=DEFAULT_CONFIG_DIR, help="Path to zmk-config repo")
    parser.add_argument("--workspace-dir", default=DEFAULT_WORKSPACE_DIR, help="Path to west workspace")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Path for output firmware (.uf2)")
    parser.add_argument("-k", "--keymap", choices=["qwerty", "colemak_dh"], default=None, help="Override keymap layout")

    args = parser.parse_args()

    # Workspace setup check
    if not os.path.exists(os.path.join(args.workspace_dir, "zephyr")):
        print(f"Initializing west workspace in {args.workspace_dir}...")
        os.makedirs(args.workspace_dir, exist_ok=True)
        west_config = os.path.join(args.workspace_dir, ".west", "config")
        os.makedirs(os.path.dirname(west_config), exist_ok=True)
        with open(west_config, "w") as f:
            f.write(f"[manifest]\npath = {os.path.relpath(os.path.join(args.config_dir, 'config'), args.workspace_dir)}\nfile = west.yml\n")
        run_cmd(["west", "update", "-n"], cwd=args.workspace_dir)

    if args.update:
        print("\033[1;34m==> Updating west workspace...\033[0m")
        run_cmd(["west", "update", "-n"], cwd=args.workspace_dir)
        if not args.targets:
            return

    if args.clean:
        build_root = os.path.join(args.workspace_dir, "build")
        if os.path.exists(build_root):
            print(f"Cleaning {build_root}...")
            shutil.rmtree(build_root)
        print("Done.")
        if not args.targets:
            return

    matrix = load_build_matrix(args.config_dir)

    if args.list:
        print("\n\033[1mAvailable targets in build.yaml:\033[0m")
        for i, t in enumerate(matrix, 1):
            name = t.get("artifact-name", f"{t.get('shield','')}-{t.get('board','')}")
            print(f"  {i}. \033[1;36m{name:<30}\033[0m board={t.get('board')} shield={t.get('shield','(none)')} format={t.get('format','bt')} snippet={t.get('snippet','-')}")
        return

    # Convert keymaps
    convert_keymaps(args.config_dir)

    # Filter targets to build
    selected_targets = []
    req_targets = [t.lower() for t in args.targets] if args.targets else ["all"]

    if "all" in req_targets:
        selected_targets = matrix
    else:
        for req in req_targets:
            matched = False
            for t in matrix:
                name = t.get("artifact-name", "").lower()
                shield = t.get("shield", "").lower()
                fmt = t.get("format", "").lower()

                if req in name or req == shield or (req == "left" and "left" in shield and "bt" in fmt) or \
                   (req == "right" and "right" in shield and "bt" in fmt) or \
                   (req == "reset" and "reset" in shield) or \
                   (req == "dongle" and fmt == "dongle"):
                    if t not in selected_targets:
                        selected_targets.append(t)
                        matched = True
            if not matched:
                print(f"\033[1;33mWarning: No target matched '{req}'. Run with -l to see available targets.\033[0m")

    if not selected_targets:
        print("No targets selected. Exiting.")
        sys.exit(1)

    built_files = []
    for t in selected_targets:
        target_copy = dict(t)
        if args.keymap:
            target_copy["keymap"] = args.keymap
        res = build_target(target_copy, args, args.config_dir, args.zmk_dir, args.workspace_dir, args.output_dir)
        if res:
            built_files.append(res)

    print("\n" + "=" * 70)
    print("\033[1;32mBuild Finished Successfully!\033[0m")
    print(f"Firmware files stored in: \033[1m{args.output_dir}\033[0m")
    for f in built_files:
        size = os.path.getsize(f)
        print(f"  • \033[1;36m{os.path.basename(f)}\033[0m ({size:,} bytes)")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
