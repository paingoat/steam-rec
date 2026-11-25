# Chạy backend: .\web\backend\run.ps1  (chạy được từ bất kỳ thư mục nào)
$env:PYTHONUTF8 = 1
Set-Location (Resolve-Path "$PSScriptRoot\..\..")
uv run --group web uvicorn main:app --app-dir web/backend --port 8000 --reload --reload-dir web/backend
