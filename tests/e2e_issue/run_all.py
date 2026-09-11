"""全E2Eスイートを順に実行（要: uv sync && uv run playwright install chromium）"""
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
SUITES = sorted(HERE.glob("test_*.py"))
failed = []
for s in SUITES:
    print(f"\n========== {s.name} ==========")
    r = subprocess.run([sys.executable, str(s)], cwd=HERE)
    if r.returncode != 0:
        failed.append(s.name)
print("\n================================")
print("ALL GREEN" if not failed else f"FAILED: {failed}")
sys.exit(1 if failed else 0)
