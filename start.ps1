param(
    [switch]$Overlay   # pass -Overlay to also launch the floating eye
)

$root = $PSScriptRoot

Write-Host "Starting Horus..." -ForegroundColor Cyan

Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Set-Location '$root\horus\backend'; Write-Host 'Horus Backend' -ForegroundColor Cyan; .\venv\Scripts\uvicorn.exe main:app --reload" `
    -WindowStyle Normal

Start-Process powershell -ArgumentList "-NoExit", "-Command", `
    "Set-Location '$root\horus\frontend'; Write-Host 'Horus Frontend' -ForegroundColor Cyan; npm start" `
    -WindowStyle Normal

if ($Overlay) {
    Write-Host "Launching overlay..." -ForegroundColor Yellow
    $pythonExe  = "$root\horus\backend\venv\Scripts\python.exe"
    $overlayScript = "$root\horus\overlay.py"
    Start-Process -FilePath $pythonExe -ArgumentList $overlayScript
    Write-Host "Overlay launched." -ForegroundColor Magenta
}

Write-Host "Done. Use -Overlay flag to also start the floating eye." -ForegroundColor Green
