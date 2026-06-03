Set-Location "$PSScriptRoot\..\horus\backend"
& ".\venv\Scripts\uvicorn.exe" main:app --reload
