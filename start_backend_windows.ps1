$ErrorActionPreference = 'Stop'
Set-Location "$PSScriptRoot\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "Edit backend\.env and add your GEMINI_API_KEY, then run this script again." -ForegroundColor Yellow; exit 0 }
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
