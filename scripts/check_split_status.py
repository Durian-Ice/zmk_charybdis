#!/usr/bin/env python3
"""
Diagnostic loop script for ZMK Split Bluetooth Connection.
Tests:
- Serial connection to /dev/ttyACM1 (Central log console)
- Central BLE scanning status
- Detection of Peripheral advertising (C9:20:6E:BE:73:A6)
- Slot reservation and GATT discovery
- Final split connection state
"""

import os
import sys
import time
import select
import subprocess

PERIPHERAL_MAC = "c9:20:6e:be:73:a6"
SPLIT_UUID_SIG = "2a 48 c2 b1"

def check_serial_logs(duration=4):
    cmd = [
        "docker", "run", "--rm", "--privileged", "-v", "/dev:/dev",
        "zmkfirmware/zmk-build-arm:stable", "python3", "-c", f"""
import os, time, select, sys
try:
    f = os.open('/dev/ttyACM1', os.O_RDWR | os.O_NONBLOCK)
    start = time.time()
    buf = ""
    lines = []
    while time.time() - start < {duration}:
        r, _, _ = select.select([f], [], [], 0.2)
        if r:
            data = os.read(f, 4096).decode('utf-8', errors='replace')
            buf += data
            parts = buf.split('\\n')
            buf = parts[-1]
            for l in parts[:-1]:
                if not any(k in l for k in ['scale_val', 'mouse_movement', 'mouse_scroll', 'apply_config', 'nrf_usbd_common', 'usb_transfer', 'z_impl_k_mutex']):
                    lines.append(l)
    os.close(f)
    for l in lines:
        print(l)
except Exception as e:
    print(f"SERIAL_ERROR: {{e}}", file=sys.stderr)
"""
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout, res.stderr

def check_peripheral_adv(duration=3):
    py_btmon = f"""
import subprocess, time, sys
p_btmon = subprocess.Popen([
    'docker', 'run', '--name', 'btmon_diag', '--rm', '--privileged', '--net=host', 'alpine',
    'sh', '-c', 'apk add --no-cache bluez-btmon >/dev/null 2>&1 && btmon'
], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

time.sleep(1.5)
p = subprocess.Popen(['bluetoothctl'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
p.stdin.write('scan le\\n')
p.stdin.flush()
time.sleep({duration})
p.stdin.write('scan off\\nexit\\n')
p.stdin.flush()
p.communicate(timeout=4)

subprocess.run(['docker', 'kill', 'btmon_diag'], capture_output=True)
out, _ = p_btmon.communicate(timeout=4)
print(out)
"""
    res = subprocess.run(["python3", "-c", py_btmon], capture_output=True, text=True)
    out = res.stdout.lower()
    adv_seen = PERIPHERAL_MAC in out or SPLIT_UUID_SIG in out
    return adv_seen, res.stdout

def main():
    print("==================================================")
    print("  ZMK Split Bluetooth Connection Feedback Loop    ")
    print("==================================================")

    # 1. Check Peripheral Advertising
    adv_seen, btmon_out = check_peripheral_adv(duration=3)
    if adv_seen:
        print(f"[✓ PASS] Peripheral ({PERIPHERAL_MAC}) is actively broadcasting split service.")
    else:
        print(f"[✗ FAIL] Peripheral ({PERIPHERAL_MAC}) NOT detected in BLE scan!")

    # 2. Check Central Serial Logs
    serial_out, serial_err = check_serial_logs(duration=3)
    if serial_err and "SERIAL_ERROR" in serial_err:
        print(f"[!] Warning: Could not read /dev/ttyACM1 ({serial_err.strip()})")

    lines = [l.strip() for l in serial_out.splitlines() if l.strip()]
    print(f"[*] Captured {len(lines)} clean log lines from Central.")

    # Search for key events
    saw_device = any("c9:20:6e:be:73:a6" in l.lower() for l in lines)
    saw_split_svc = any("found the split service" in l.lower() or "found split service" in l.lower() for l in lines)
    saw_slot_err = any("unable to reserve peripheral slot" in l.lower() for l in lines)
    saw_conn_init = any("initiating new connection" in l.lower() for l in lines)
    saw_connected = any("connected:" in l.lower() and "c9:20:6e:be:73:a6" in l.lower() for l in lines)

    print("\n--- Central State Diagnostics ---")
    print(f"  • Central saw peripheral MAC:        {saw_device}")
    print(f"  • Central matched split service UUID: {saw_split_svc}")
    print(f"  • Slot reservation error:             {saw_slot_err}")
    print(f"  • Connection initiated:               {saw_conn_init}")
    print(f"  • Central-Peripheral connected:      {saw_connected}")

    if lines:
        print("\n--- Recent Relevant Central Logs ---")
        for l in lines[-20:]:
            print(f"  {l}")

    # Verdict
    print("\n==================================================")
    if saw_connected:
        print("  STATUS: GREEN (Split is connected!)")
        print("==================================================")
        sys.exit(0)
    else:
        print("  STATUS: RED (Split is NOT connected)")
        print("==================================================")
        sys.exit(1)

if __name__ == "__main__":
    main()
