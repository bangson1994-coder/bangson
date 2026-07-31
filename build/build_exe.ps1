$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
& .\.venv\Scripts\python.exe -m pytest

# --onedir: không phải giải nén gần 100 MB mỗi lần mở, khởi động nhanh hơn --onefile.
& .\.venv\Scripts\pyinstaller.exe `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name "Doi-PDF-sang-Word-Bang-Son" `
    --collect-all keyring `
    --collect-all google.genai `
    --collect-all PIL `
    --hidden-import keyring.backends.Windows `
    --hidden-import fitz `
    ai_office_vietnam\main.py

Compress-Archive `
    -Path "dist\Doi-PDF-sang-Word-Bang-Son" `
    -DestinationPath "dist\Doi-PDF-sang-Word-Bang-Son-Portable.zip" `
    -Force

Write-Host "Hoan tat: dist\Doi-PDF-sang-Word-Bang-Son-Portable.zip" -ForegroundColor Green
