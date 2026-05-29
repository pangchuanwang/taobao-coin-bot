# 本地使用说明

核心脚本：`淘金币任务.py`

日常建议直接运行 `run_daily_taobao.py`。

## 1. 准备环境

1. 安装 Python 3。
2. 在手机上开启“开发者选项”和“USB 调试”。
3. 用数据线连接手机，并在手机上允许 USB 调试授权。

当前工作区安装依赖后会自带一份 `adb.exe`。如果系统里没有单独安装 Android Platform Tools，也可以先直接使用项目自带的版本继续操作。

## 2. 安装依赖

在当前目录执行：

```powershell
.\setup.ps1
```

脚本会：

- 创建 `.venv`
- 升级 `pip`
- 按 `requirements.txt` 安装依赖
- 检查当前机器是否能找到 `adb`

当前工作区把 `ddddocr` 从上游的 `1.5.6` 调整为 `1.6.1`，这样可以兼容本机已安装的 Python 3.13。

## 3. 首次连机检查

先确认电脑能识别手机：

```powershell
.\.venv\Lib\site-packages\adbutils\binaries\adb.exe devices
```

如果能看到设备序列号，再执行：

```powershell
.\.venv\Scripts\python.exe -m uiautomator2 init
```

## 4. 每日运行

```powershell
.\run_daily_taobao.ps1
```

如果只想单独运行：

```powershell
.\.venv\Scripts\python.exe .\淘金币任务.py
```

## 5. 使用建议

- 执行前先把淘宝登录好，避免脚本中途卡在登录页。
- 平台页面经常改版，若突然失效，优先检查脚本里依赖的按钮文案或页面结构是否变化。
