"""Isolated acceptance suite; does not connect to real security systems."""

import subprocess
import sys

for args in [
    ["-m", "pytest", "-q", "--tb=short"],
    ["-m", "ruff", "check", "app", "tests", "migrations", "scripts"],
    ["scripts/smoke_http.py"],
    ["-m", "app.soar.simulator", "playbooks/block_ip_lab.yml"],
    ["-m", "app.soar.simulator", "playbooks/suspend_test_process.yml"],
]:
    subprocess.run([sys.executable, *args], check=True)
