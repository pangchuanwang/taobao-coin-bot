$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$bundledAdb = Join-Path $root ".venv\Lib\site-packages\adbutils\binaries\adb.exe"

Write-Host "Checking Python..."
python --version

Write-Host "Checking adb..."
if (-not (Get-Command adb -ErrorAction SilentlyContinue)) {
    if (Test-Path $bundledAdb) {
        $env:Path = "$(Split-Path -Parent $bundledAdb);$env:Path"
        Write-Host "Using bundled adb from the virtual environment."
    } else {
        Write-Warning "adb was not found. Install Android Platform Tools and add adb to PATH first."
    }
}

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment..."
    python -m venv (Join-Path $root ".venv")
}

Write-Host "Upgrading pip..."
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Installing project dependencies..."
& $venvPython -m pip install -r (Join-Path $root "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if (-not (Get-Command adb -ErrorAction SilentlyContinue) -and (Test-Path $bundledAdb)) {
    $env:Path = "$(Split-Path -Parent $bundledAdb);$env:Path"
    Write-Host "Using bundled adb from the virtual environment."
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "After connecting a phone, run:"
Write-Host "  .\.venv\Scripts\python.exe .\run_daily_taobao.py"
