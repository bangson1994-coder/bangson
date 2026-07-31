$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
& .\.venv\Scripts\python.exe -m pytest

& .\.venv\Scripts\pyinstaller.exe `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "AI-Office-Viet-Nam" `
    --collect-all keyring `
    --collect-all google.genai `
    --hidden-import keyring.backends.Windows `
    --hidden-import fitz `
    ai_office_vietnam\main.py

Write-Host "Hoan tat: dist\AI-Office-Viet-Nam.exe" -ForegroundColor Green
