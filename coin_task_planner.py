from __future__ import annotations

import json
import re
import time
from datetime import date, datetime
from pathlib import Path
from statistics import median
from typing import Any

from utils import classify_coin_task, label_coin_task


ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "logs" / "coin_task_catalog.json"
DAILY_DISCOVERY_PATH = ROOT / "logs" / "coin_task_discovery_latest.json"
STATS_PATH = ROOT / "logs" / "coin_task_stats.json"
MAX_TASK_SAMPLES = 20

TASK_HANDLER_OVERRIDES = {
    "好物沉浸看": {"handler": "deep_browse", "estimated_seconds": 12},
    "淘金币趣味课堂": {"handler": "quiz", "estimated_seconds": 25},
    "来淘宝闪购分百亿补贴": {"handler": "event_browse", "estimated_seconds": 10},
    "发现精选好物": {"handler": "browse", "estimated_seconds": 12},
    "领红包搜心仪商品可用": {"handler": "search_browse", "estimated_seconds": 10},
    "天天签到免费拿IP周边": {"handler": "browse", "estimated_seconds": 10},
    "逛逛金币抵钱好货": {"handler": "browse", "estimated_seconds": 10},
    "去蚂蚁庄园捐爱心蛋": {"handler": "cross_app_claim", "estimated_seconds": 30},
    "去闲鱼币领现金红包": {"handler": "cross_app_browse", "estimated_seconds": 25},
}

TASK_ESTIMATED_SECONDS = {
    "签到类": 5,
    "领取类": 5,
    "浏览商品": 12,
    "搜索浏览": 18,
    "浏览店铺": 15,
    "活动会场": 15,
    "金币庄园": 25,
    "内容浏览": 25,
    "小游戏": 40,
    "答题类": 25,
    "外部应用": 35,
}

TASK_NAME_ALIASES = {
    "天天签到免费拿IP周边": "天天签到免费拿IP周边",
    "领红包搜心仪商品可用": "领红包搜心仪商品可用",
    "逛逛金币抵钱好货": "逛逛金币抵钱好货",
}

PROGRESS_RE = re.compile(r"^(?P<name>.*?)(?:\((?P<done>\d+)\s*/\s*(?P<total>\d+)\))?$")
REWARD_RE = re.compile(r"\+?\s*(?P<low>\d+)(?:\s*[~\-]\s*(?P<high>\d+))?")
SECONDS_RE = re.compile(r"浏览\s*(?P<seconds>\d+)\s*秒")


def normalize_task_name(text: str) -> str:
    text = text.strip().replace(" ", "")
    match = PROGRESS_RE.match(text)
    if match:
        text = match.group("name")
    return TASK_NAME_ALIASES.get(text, text)


def parse_progress(text: str) -> tuple[int | None, int | None]:
    match = PROGRESS_RE.match(text.strip().replace(" ", ""))
    if not match or match.group("done") is None:
        return None, None
    return int(match.group("done")), int(match.group("total"))


def parse_reward(subtitle: str = "", reward_text: str = "") -> int:
    explicit_reward = _parse_reward_text(reward_text)
    if explicit_reward:
        return explicit_reward
    return _parse_reward_text(subtitle)


def _parse_reward_text(text: str) -> int:
    reward = 0
    if not text:
        return reward
    cleaned = text.replace("十", "+")
    for match in REWARD_RE.finditer(cleaned):
        low = int(match.group("low"))
        high = int(match.group("high")) if match.group("high") else low
        reward = max(reward, high)
    return reward


def infer_estimated_seconds(task_name: str, subtitle: str, category: str) -> int:
    override = TASK_HANDLER_OVERRIDES.get(task_name)
    if override:
        return override["estimated_seconds"]

    match = SECONDS_RE.search(subtitle or "")
    if match:
        return max(5, int(match.group("seconds")) + 5)

    return TASK_ESTIMATED_SECONDS.get(category, 30)


def infer_handler(task_name: str, category: str) -> str:
    override = TASK_HANDLER_OVERRIDES.get(task_name)
    if override:
        return override["handler"]

    if category in {"浏览商品", "搜索浏览", "浏览店铺", "活动会场", "内容浏览"}:
        return "browse"
    if category in {"签到类", "领取类"}:
        return "claim"
    if category == "小游戏":
        return "game"
    return "unknown"


def estimate_score(reward: int, estimated_seconds: int, policy: dict[str, Any]) -> float:
    if policy["action"] != "do":
        return -1.0
    if reward <= 0:
        reward = 1
    return round(reward / max(estimated_seconds, 1), 4)


def load_stats() -> dict[str, Any]:
    if not STATS_PATH.exists():
        return {"tasks": {}}
    return json.loads(STATS_PATH.read_text(encoding="utf-8"))


def save_stats(stats: dict[str, Any]) -> None:
    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATS_PATH.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")


def summarize_task_stats(task_name: str) -> dict[str, Any]:
    samples = load_stats().get("tasks", {}).get(task_name, {}).get("samples", [])
    success_samples = [sample for sample in samples if sample["verified"]]
    reward_samples = [sample["reward"] for sample in success_samples if sample["reward"] > 0]
    if not samples:
        return {
            "sample_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "success_rate": None,
            "median_seconds": None,
            "median_reward": None,
        }

    return {
        "sample_count": len(samples),
        "success_count": len(success_samples),
        "failure_count": len(samples) - len(success_samples),
        "success_rate": round(len(success_samples) / len(samples), 4),
        "median_seconds": round(median(sample["seconds"] for sample in success_samples), 2) if success_samples else None,
        "median_reward": round(median(reward_samples), 2) if reward_samples else None,
    }


def record_task_outcome(
    task: dict[str, Any],
    *,
    seconds: float,
    reward: int,
    verified: bool,
    progress_delta: int,
    note: str = "",
) -> None:
    stats = load_stats()
    entry = stats.setdefault("tasks", {}).setdefault(task["task_name"], {"samples": []})
    entry["samples"].append(
        {
            "recorded_at": datetime.now().isoformat(timespec="seconds"),
            "seconds": round(seconds, 2),
            "reward": reward,
            "verified": verified,
            "progress_delta": progress_delta,
            "note": note,
        }
    )
    entry["samples"] = entry["samples"][-MAX_TASK_SAMPLES:]
    save_stats(stats)


def build_task_record(task_name: str, subtitle: str = "", button_text: str = "", reward_text: str = "") -> dict[str, Any]:
    normalized_name = normalize_task_name(task_name)
    done, total = parse_progress(task_name)
    policy = classify_coin_task(normalized_name)
    labels = label_coin_task(normalized_name)
    reward = parse_reward(subtitle, reward_text)
    category = policy["category"]
    handler = infer_handler(normalized_name, category)
    estimated_seconds = infer_estimated_seconds(normalized_name, subtitle, category)
    learning = summarize_task_stats(normalized_name)
    effective_seconds = learning["median_seconds"] or estimated_seconds
    effective_reward = learning["median_reward"] or reward
    score = estimate_score(effective_reward, effective_seconds, policy)
    return {
        "task_name": normalized_name,
        "raw_task_name": task_name,
        "subtitle": subtitle,
        "button_text": button_text,
        "reward": reward,
        "done": done,
        "total": total,
        "action": policy["action"],
        "category": category,
        "reason": policy["reason"],
        "labels": labels,
        "estimated_seconds": estimated_seconds,
        "effective_seconds": effective_seconds,
        "effective_reward": effective_reward,
        "handler": handler,
        "score": score,
        "stats": learning,
    }


def prioritize_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        tasks,
        key=lambda task: (
            task["action"] != "do",
            -task["score"],
            task["estimated_seconds"],
            -task["reward"],
            task["task_name"],
        ),
    )


def load_catalog() -> dict[str, Any]:
    if not CATALOG_PATH.exists():
        return {"last_scan_date": None, "tasks": {}}
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def save_catalog(catalog: dict[str, Any]) -> None:
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")


def refresh_catalog(tasks: list[dict[str, Any]], scan_date: date | None = None) -> dict[str, Any]:
    scan_date = scan_date or date.today()
    catalog = load_catalog()
    old_tasks = catalog.get("tasks", {})
    current_names = {task["task_name"] for task in tasks}
    old_names = set(old_tasks)

    new_names = sorted(current_names - old_names)
    removed_names = sorted(old_names - current_names)

    now = datetime.now().isoformat(timespec="seconds")
    active_tasks = {}
    for task in tasks:
        previous = old_tasks.get(task["task_name"], {})
        active_tasks[task["task_name"]] = {
            **previous,
            **task,
            "first_seen": previous.get("first_seen", now),
            "last_seen": now,
        }

    catalog = {
        "last_scan_date": scan_date.isoformat(),
        "tasks": active_tasks,
    }
    save_catalog(catalog)

    discovery = {
        "scan_date": scan_date.isoformat(),
        "new_tasks": new_names,
        "removed_tasks": removed_names,
        "needs_exploration": [
            task["task_name"]
            for task in prioritize_tasks(tasks)
            if task["task_name"] in new_names and (task["action"] == "review" or task["handler"] == "unknown")
        ],
        "tasks": prioritize_tasks(tasks),
    }
    DAILY_DISCOVERY_PATH.write_text(json.dumps(discovery, ensure_ascii=False, indent=2), encoding="utf-8")
    return discovery


def is_first_scan_today(scan_date: date | None = None) -> bool:
    scan_date = scan_date or date.today()
    return load_catalog().get("last_scan_date") != scan_date.isoformat()


DAILY_REPORT_JSON = ROOT / "logs" / "daily-report-{date}.json"
DAILY_REPORT_TXT = ROOT / "logs" / "daily-report-{date}.txt"


class RunTracker:
    def __init__(self):
        self.start_time = time.time()
        self.identified_count = 0
        self.completed_tasks = []
        self.skipped_tasks = []
        self.new_tasks = []
        self.failed_tasks = []

    def set_identified(self, count: int):
        self.identified_count = count

    def record_completed(self, task_name: str, category: str, reward: int, seconds: float, progress_delta: int):
        self.completed_tasks.append({
            "task_name": task_name,
            "category": category,
            "reward": reward,
            "seconds": round(seconds, 2),
            "progress_delta": progress_delta,
        })

    def record_skipped(self, task_name: str, category: str, reason: str):
        self.skipped_tasks.append({
            "task_name": task_name,
            "category": category,
            "reason": reason,
        })

    def record_new(self, task_names: list[str]):
        self.new_tasks = task_names

    def record_failed(self, task_name: str, category: str):
        self.failed_tasks.append({
            "task_name": task_name,
            "category": category,
        })

    def generate_report(self):
        elapsed = time.time() - self.start_time
        minutes, seconds = divmod(int(elapsed), 60)
        total_reward = sum(t["reward"] for t in self.completed_tasks)
        report = {
            "date": date.today().isoformat(),
            "identified_count": self.identified_count,
            "completed_count": len(self.completed_tasks),
            "completed_tasks": self.completed_tasks,
            "skipped_count": len(self.skipped_tasks),
            "skipped_tasks": self.skipped_tasks,
            "new_count": len(self.new_tasks),
            "new_tasks": self.new_tasks,
            "failed_count": len(self.failed_tasks),
            "failed_tasks": self.failed_tasks,
            "total_reward": total_reward,
            "elapsed_seconds": round(elapsed, 2),
        }
        date_str = date.today().strftime("%Y%m%d")
        json_path = Path(str(DAILY_REPORT_JSON).format(date=date_str))
        txt_path = Path(str(DAILY_REPORT_TXT).format(date=date_str))
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        txt_path.write_text(_format_report_text(report, minutes, seconds), encoding="utf-8")
        print(f"\n日报已生成：{json_path.name}、{txt_path.name}")


def _format_report_text(report: dict, minutes: int, seconds: int) -> str:
    lines = [
        f"淘宝金币任务日报 - {report['date']}",
        "=" * 40,
        "",
        f"识别任务总数：{report['identified_count']}",
        f"已完成（已验证）：{report['completed_count']}",
        f"跳过任务：{report['skipped_count']}",
        f"今日新任务：{report['new_count']}",
        f"执行失败：{report['failed_count']}",
        f"总收益（已验证）：{report['total_reward']} 金币",
        f"总耗时：{minutes} 分 {seconds} 秒",
    ]
    if report["completed_tasks"]:
        lines += ["", "--- 已完成任务 ---"]
        for t in report["completed_tasks"]:
            lines.append(f"  [{t['category']}] {t['task_name']}：+{t['reward']}金币，{t['seconds']}秒")
    if report["skipped_tasks"]:
        lines += ["", "--- 跳过任务 ---"]
        for t in report["skipped_tasks"]:
            lines.append(f"  [{t['category']}] {t['task_name']}：{t['reason']}")
    if report["new_tasks"]:
        lines += ["", "--- 今日新任务 ---"]
        for name in report["new_tasks"]:
            lines.append(f"  {name}")
    if report["failed_tasks"]:
        lines += ["", "--- 执行失败 ---"]
        for t in report["failed_tasks"]:
            lines.append(f"  [{t['category']}] {t['task_name']}")
    return "\n".join(lines) + "\n"
