$frontendCommand = "Set-Location 'e:\maritime_application2\frontend'; npm run dev"
$backendCommand = "Set-Location 'e:\maritime_application2\backend'; python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

Start-Process -FilePath "C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -ArgumentList "-NoLogo", "-NoProfile", "-Command", $backendCommand

Start-Sleep -Seconds 2

Start-Process -FilePath "C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -ArgumentList "-NoLogo", "-NoProfile", "-Command", $frontendCommand
