# 淘宝淘金币自动任务

使用 uiautomator2 自动完成淘宝淘金币日常任务，支持任务自动发现、优先级排序、执行验证和每日报告。

## 环境要求

- Windows 10/11
- Python 3.10+
- 安卓手机 + USB 数据线

## 快速开始

### 1. 开启手机 USB 调试

1. 手机进入 **设置 → 关于手机**，连续点击"版本号" 7 次，开启开发者模式
2. 进入 **设置 → 开发者选项**，打开 **USB 调试**
3. 用数据线连接电脑，手机弹窗选择 **允许 USB 调试**

### 2. 安装依赖

打开 PowerShell，进入项目目录，执行：

```powershell
cd taobao
.\setup.ps1
```

脚本会自动：
- 创建 Python 虚拟环境（`.venv`）
- 安装所有依赖
- 检查 ADB 是否可用（项目自带一份，无需单独安装）

### 3. 首次连接手机

确认电脑识别到手机：

```powershell
.\.venv\Lib\site-packages\adbutils\binaries\adb.exe devices
```

看到设备序列号（如 `497e26a2  device`）即为成功。然后初始化 uiautomator2：

```powershell
.\.venv\Scripts\python.exe -m uiautomator2 init
```

### 4. 每日运行

确保手机已亮屏解锁、淘宝已登录，然后执行：

```powershell
.\run_daily_taobao.ps1
```

脚本会自动打开淘宝、进入淘金币任务页、逐个完成任务，完成后生成运行报告。

## 运行输出

### 日志

运行日志保存在 `logs\daily-run-{yyyyMMdd-HHmmss}.log`。

### 每日报告

每次运行结束后自动生成两份报告：

| 文件 | 说明 |
|------|------|
| `logs\daily-report-{yyyyMMdd}.json` | 结构化数据，可供程序读取 |
| `logs\daily-report-{yyyyMMdd}.txt` | 人可读的文本摘要 |

报告包含以下字段：

| 字段 | 说明 |
|------|------|
| identified_count | 本次识别到的任务总数 |
| completed_count / completed_tasks | 已验证完成的任务（名称、分类、奖励、耗时） |
| skipped_count / skipped_tasks | 跳过的任务（含跳过原因） |
| new_count / new_tasks | 今日新发现的任务 |
| failed_count / failed_tasks | 执行后未通过验证的任务 |
| total_reward | 已验证任务的总金币收益 |
| elapsed_seconds | 总耗时 |

### 任务学习数据

- `logs\coin_task_stats.json` — 任务历史执行样本（耗时、奖励、成功率），用于优化后续执行效率
- `logs\coin_task_catalog.json` — 任务目录，记录所有见过的任务及首次/末次出现时间

## 项目结构

```
├── 淘金币任务.py          # 主脚本，负责任务发现、调度、执行、验证
├── coin_task_planner.py    # 任务规划器：目录管理、统计学习、优先级排序、报告生成
├── coin_task_handlers.py   # 任务处理器：按任务类型（浏览、签到、答题等）执行具体操作
├── utils.py                # 工具函数：设备连接、任务分类规则、UI 操作、验证码识别
├── run_daily_taobao.py     # 日常运行入口
├── run_daily_taobao.ps1    # PowerShell 运行脚本（自动配置 ADB 路径、记录日志）
├── setup.ps1               # 一键安装脚本
├── requirements.txt        # Python 依赖
└── logs/                   # 运行日志、报告、统计数据
```

## 常见问题

**Q: 提示"禁止运行脚本"**

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

输入 `Y` 确认后重新运行。

**Q: 提示"未检测到任何连接的安卓设备"**

- 检查数据线是否支持数据传输（部分线只能充电）
- 手机是否弹出了 USB 调试授权窗口
- 运行 `adb devices` 确认设备状态为 `device`（不是 `unauthorized`）

**Q: 任务突然不生效了**

淘宝页面经常改版，如果按钮文案或页面结构变化，需要更新脚本中对应的定位规则。

**Q: 运行中可以操作手机吗**

不可以。脚本通过 ADB 控制手机界面，手动操作会导致脚本失控。建议运行期间将手机放在一旁。
