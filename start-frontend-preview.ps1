[CmdletBinding()]
param(
  [int]$Port = 5173,
  [ValidateSet("main", "hitl")]
  [string]$Mode = "main"
)

Set-Location "E:\maritime_application2\frontend"
$env:VITE_APP_MODE = $Mode
npm run build
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

npx vite preview --host 0.0.0.0 --port $Port
