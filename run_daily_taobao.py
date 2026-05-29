import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCRIPTS = [
    "淘金币任务.py",
]


def run_script(script_name: str) -> int:
    script_path = ROOT / script_name
    if not script_path.exists():
        print(f"[跳过] 未找到脚本: {script_name}")
        return 1

    print(f"\n[开始] {script_name}")
    completed = subprocess.run([sys.executable, str(script_path)], cwd=ROOT)
    if completed.returncode == 0:
        print(f"[完成] {script_name}")
    else:
        print(f"[失败] {script_name}，退出码 {completed.returncode}")
    return completed.returncode


def main() -> int:
    print("开始执行淘宝日常任务：淘金币 + 芭芭农场")
    failures = []
    for script in SCRIPTS:
        if run_script(script) != 0:
            failures.append(script)
            break
    if failures:
        print("\n以下脚本执行失败：")
        for script in failures:
            print(f"- {script}")
        return 1

    print("\n全部日常任务执行完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
