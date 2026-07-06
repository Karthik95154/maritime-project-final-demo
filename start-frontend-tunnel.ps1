[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$TunnelHost,

  [int]$Port = 5173,

  [ValidateSet("main", "hitl")]
  [string]$Mode = "main"
)

$env:TUNNEL_HOST = $TunnelHost
$env:VITE_APP_MODE = $Mode
Set-Location "E:\maritime_application2\frontend"
npm run dev -- --host 0.0.0.0 --port $Port
