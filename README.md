# taobao-coin-bot

English | [简体中文](README.zh-CN.md)

An Android UI automation tool for learning and research purposes, built with Python and uiautomator2. Automates repetitive daily tasks in the Taobao app through ADB device control, with task discovery, priority scoring, execution verification, and daily reporting.

> **Disclaimer:** This project is for personal learning and research on Android UI automation. Users are responsible for complying with all applicable platform terms of service. This is not a commercial product and makes no guarantees about outcomes.

---

## Overview

taobao-coin-bot connects to an Android phone via USB/ADB, launches the Taobao app, navigates to the daily rewards page, and automates the workflow of discovering available tasks, scoring them by efficiency, executing them in priority order, and verifying completion.

The tool demonstrates practical Android UI automation techniques including element finding, gesture simulation, OCR, template matching, cross-app navigation, and CAPTCHA handling.

## Features

### Task Discovery
- Scans the task page by scrolling, extracting task names, subtitles, rewards, and progress from Android UI elements
- Maintains a persistent task catalog tracking first-seen and last-seen dates
- Detects new and removed tasks daily; flags unknown tasks for later analysis

### Priority Scoring
- Each task scored by `reward / estimated_seconds`
- Tasks requiring payment, orders, social invites, or authorization are automatically skipped
- Historical execution data (duration, reward, success rate) refines future estimates

### Task Handlers
- **Browse**: Timed scroll through product/event pages
- **Claim**: Sign-in and reward collection
- **Search Browse**: Wait for search results, scroll, return
- **Deep Browse**: Product detail page immersion with slow scroll
- **Event Browse**: Promotional event pages (scroll only, no purchases)
- **Quiz**: Detect answer options, click one, claim reward
- **Cross-App**: Navigate to Alipay/Xianyu for partner tasks, then recover back to Taobao

### Execution Verification
- Re-scans the task list after each execution to confirm progress increased
- Records success/failure samples for continuous learning

### Daily Reports
- Generates JSON + text summary reports per run
- Tracks: completed, skipped, failed, new tasks; total reward; elapsed time

### Cross-App Navigation
- 3-phase recovery strategy for returning from external apps (Alipay, Xianyu, Tmall)
- Phase 1: press back / pull Taobao to foreground
- Phase 2: restart Taobao entirely
- Phase 3: fallback to task page

### CAPTCHA Handling
- Detects slide-to-verify CAPTCHAs and performs automated slide gestures

## Tech Stack

- **Language:** Python 3.10+
- **Android Automation:** uiautomator2 (3.5.0) — drives phone UI via ADB
- **ADB:** adbutils (bundled with uiautomator2)
- **OCR:** ddddocr (1.6.1) — Chinese text recognition on screenshots
- **Image Recognition:** OpenCV (4.13.0.92) — multi-scale template matching for button detection
- **License:** Apache 2.0

## Project Structure

```
淘金币任务.py            — Main script: task discovery, scheduling, execution, verification
coin_task_planner.py     — Task planner: catalog management, stats learning, priority sorting, reports
coin_task_handlers.py    — Task handlers: browse, claim, quiz, cross-app, etc.
utils.py                 — Utilities: device connection, task classification rules, UI operations, OCR
run_daily_taobao.py      — Daily run entry point
run_daily_taobao.ps1     — PowerShell runner (auto-configures ADB path, logging)
setup.ps1                — One-click setup script (venv, dependencies, ADB check)
requirements.txt         — Python dependencies
```

## Getting Started

### Prerequisites

- Windows 10/11
- Python 3.10+
- Android phone with USB debugging enabled
- USB data cable

### Setup

1. Enable USB debugging on your phone: Settings → About Phone → tap Build Number 7 times → Developer Options → USB Debugging
2. Connect phone via USB and authorize the debugging prompt
3. Run setup:

```powershell
.\setup.ps1
```

This creates a virtual environment, installs dependencies, and checks for ADB.

4. Verify device connection:

```powershell
.\.venv\Lib\site-packages\adbutils\binaries\adb.exe devices
```

5. Initialize uiautomator2 on the phone:

```powershell
.\.venv\Scripts\python.exe -m uiautomator2 init
```

### Daily Run

Ensure the phone is unlocked and Taobao is logged in, then:

```powershell
.\run_daily_taobao.ps1
```

Logs are saved to `logs/`.

## Usage

The tool automatically:
1. Opens Taobao and navigates to the coin task page
2. Scans all available tasks
3. Scores and prioritizes them
4. Executes tasks in priority order
5. Verifies each task's completion
6. Generates a daily report

**Important:** Do not interact with the phone during execution — the tool controls the UI via ADB.

## Highlights

- **Decorator-based handler registry**: New task types can be added by simply decorating a function
- **Learning from history**: Task outcomes (duration, reward, success) are persisted and used to improve future estimates
- **Multi-signal classification**: Tasks are classified by 11 priority categories, 5 skip categories, and 10 label types
- **Robust cross-app recovery**: 3-phase strategy with timeout deadlines for returning from external apps
- **Human-like behavior**: Randomized swipe coordinates, durations, and wait intervals to reduce detection risk
- **Comprehensive reporting**: Structured JSON + human-readable text reports for each run

## Roadmap

- Support more task types as Taobao updates its UI
- Add scheduling support (e.g., daily cron)
- Improve quiz answer accuracy
- Add web dashboard for report visualization
- Cross-platform support (macOS/Linux)

## Author

Chuanwang Pang
GitHub: [github.com/pangchuanwang](https://github.com/pangchuanwang)

## License

Apache 2.0
