# TBA local Windows setup (PowerShell). Run from the project root:
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
# For a normal shell, use: .\scripts\setup_windows.ps1 (when your policy allows it).
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Python Launcher (py) not found. Install Python 3.11 from python.org, with Python Launcher enabled.'
}
& py -3.11 --version
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 is required for the recommended local setup.' }
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    & py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv.' }
}
$venvPy = '.\.venv\Scripts\python.exe'
& $venvPy -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
& $venvPy -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Installing dependencies failed.' }
Write-Host ''
Write-Host 'TBA ready. Start: .\.venv\Scripts\python.exe app.py'
Write-Host 'Then open: http://127.0.0.1:5000'
Write-Host 'Optional offline Piper voice models are NOT installed by this script.'
