$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$bundledAdbDir = Join-Path $root ".venv\Lib\site-packages\adbutils\binaries"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$logDir = Join-Path $root "logs"
$logPath = Join-Path $logDir ("daily-run-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()

if (Test-Path (Join-Path $bundledAdbDir "adb.exe")) {
    $env:Path = "$bundledAdbDir;$env:Path"
}

if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

Write-Host "Logging to $logPath"
& $venvPython (Join-Path $root "run_daily_taobao.py") 2>&1 | ForEach-Object {
    $_
    $_ | Out-File -FilePath $logPath -Append -Encoding utf8
}
