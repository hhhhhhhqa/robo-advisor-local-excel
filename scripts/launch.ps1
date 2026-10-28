param([ValidateSet('setup', 'update')][string]$Action = 'update')
$ErrorActionPreference = 'Stop'
$AppRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $AppRoot
$env:UV_CACHE_DIR = Join-Path $AppRoot '.runtime\cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $AppRoot '.runtime\python'
$env:UV_PYTHON_BIN_DIR = Join-Path $AppRoot '.runtime\bin'
$env:UV_PROJECT_ENVIRONMENT = Join-Path $AppRoot '.venv'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$UvApp = Join-Path $AppRoot '.tools\uv.exe'
$PythonApp = Join-Path $AppRoot '.venv\Scripts\python.exe'
try {
    if (-not (Test-Path -LiteralPath $UvApp)) {
        New-Item -ItemType Directory -Force -Path (Join-Path $AppRoot '.tools') | Out-Null
        Write-Host 'Preparing the local Python installer (internet required)...'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $Installer = Join-Path $AppRoot '.tools\install-uv.ps1'
        Invoke-WebRequest -UseBasicParsing -Uri 'https://astral.sh/uv/0.13.6/install.ps1' -OutFile $Installer
        $env:UV_UNMANAGED_INSTALL = Join-Path $AppRoot '.tools'
        & $Installer
        if (-not (Test-Path -LiteralPath $UvApp)) { throw 'Installer did not create uv.exe.' }
    }
    if ($Action -eq 'setup' -or -not (Test-Path -LiteralPath $PythonApp)) {
        Write-Host 'Preparing Python and dependencies in this folder...'
        & $UvApp sync --frozen --no-dev --no-install-project --python 3.12 --managed-python
        if ($LASTEXITCODE -ne 0) { throw 'Python setup failed. Check your internet connection and rerun 1_Setup.' }
    }
    & $PythonApp (Join-Path $AppRoot 'local_runner.py') $Action
    exit $LASTEXITCODE
} catch {
    Write-Host "Failed: $_" -ForegroundColor Red
    Write-Host 'Extract the complete ZIP, check your internet connection, and try again.'
    exit 1
}
