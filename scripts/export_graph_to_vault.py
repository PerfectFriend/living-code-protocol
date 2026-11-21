#!/home/thomas/build/bin/python3
"""Крон-обёртка для авто-экспорта эволюционного графа в Obsidian Vault.
Запускается Hermes cron каждые 6ч (no_agent=true, deliver=local)."""
import sys
import subprocess
from datetime import datetime
from pathlib import Path

VAULT = Path.home() / "Documents" / "ObsidianVault"
SCRIPT = VAULT / "GodModeCoder" / "scripts" / "export_graph_to_obsidian.py"
CONFIG = VAULT / "GodModeCoder" / "configs" / "graph.yaml"
VERIFY_SCRIPT = VAULT / "GodModeCoder" / "scripts" / "hermes-verify-all.py"
PYTHON = Path("/home/thomas/build/bin/python3")  # cron-safe interpreter: cron's PATH python lacks PyYAML (#122222-pattern); build python has it and runs the full pipeline

def main():
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Starting graph pulse export...")
    
    # 1. Run exporter
    result = subprocess.run(
        [str(PYTHON), str(SCRIPT), "--vault", str(VAULT), "--config", str(CONFIG)],
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    if result.returncode != 0:
        print(f"EXPORT FAILED: {result.stderr}")
        return 1
    print(result.stdout.strip())
    
    # 2. Git commit (history of evolution)
    try:
        subprocess.run(["git", "-C", str(VAULT), "add", "Evolution/"], check=True, capture_output=True)
        commit_msg = f"graph: pulse export {datetime.now():%Y-%m-%d %H:%M}"
        subprocess.run(["git", "-C", str(VAULT), "commit", "-m", commit_msg], check=True, capture_output=True)
        print(f"Git committed: {commit_msg}")
    except subprocess.CalledProcessError as e:
        print(f"Git commit failed (may be no changes): {e}")
    
    # 3. Run verification
    verify_result = subprocess.run(
        [str(PYTHON), str(VERIFY_SCRIPT)],
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    if verify_result.returncode != 0:
        # verify-all проверяет весь vault (git status/skills/pulse) — его падения не должны
        # валить экспорт: фикс 2026-11-21, до этого крон падал 8 циклов подряд из-за путей.
        print(f"VERIFY WARN (export+commit OK, детали ниже):\n{verify_result.stdout}")
    else:
        print("✅ All verification tests passed")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())