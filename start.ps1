$root = $PSScriptRoot

Write-Host "Starting Horus..." -ForegroundColor Cyan

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\horus\backend'; Write-Host 'Horus Backend' -ForegroundColor Cyan; .\venv\Scripts\uvicorn.exe main:app --reload" -WindowStyle Normal

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\horus\frontend'; Write-Host 'Horus Frontend' -ForegroundColor Cyan; npm start" -WindowStyle Normal

Write-Host "Backend and frontend launched in separate windows." -ForegroundColor Green
