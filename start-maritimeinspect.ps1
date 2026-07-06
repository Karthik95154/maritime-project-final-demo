[CmdletBinding()]
param(
  [switch]$StartHitl,
  [ValidateSet("dev", "preview")]
  [string]$FrontendMode = "preview"
)

$backendCommand = "Set-Location 'E:\maritime_application2\backend'; python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

if ($FrontendMode -eq "preview") {
  $frontendCommand = "Set-Location 'E:\maritime_application2'; powershell -ExecutionPolicy Bypass -File '.\start-frontend-preview.ps1' -Port 5173 -Mode main"
  $hitlCommand = "Set-Location 'E:\maritime_application2'; powershell -ExecutionPolicy Bypass -File '.\start-frontend-preview.ps1' -Port 5174 -Mode hitl"
} else {
  $frontendCommand = "Set-Location 'E:\maritime_application2\frontend'; `$env:BACKEND_TARGET='http://127.0.0.1:8000'; `$env:VITE_APP_MODE='main'; npm run dev -- --host 0.0.0.0 --port 5173"
  $hitlCommand = "Set-Location 'E:\maritime_application2\frontend'; `$env:BACKEND_TARGET='http://127.0.0.1:8000'; `$env:VITE_APP_MODE='hitl'; npm run dev -- --host 0.0.0.0 --port 5174"
}

Start-Process -FilePath "C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -ArgumentList "-NoLogo", "-NoProfile", "-Command", $backendCommand

Start-Sleep -Seconds 2

Start-Process -FilePath "C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -ArgumentList "-NoLogo", "-NoProfile", "-Command", $frontendCommand

if ($StartHitl) {
  Start-Sleep -Seconds 2

  Start-Process -FilePath "C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -ArgumentList "-NoLogo", "-NoProfile", "-Command", $hitlCommand
}
