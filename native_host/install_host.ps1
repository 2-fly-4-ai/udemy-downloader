param(
  [Parameter(Mandatory=$false)] [string]$ExtensionId
)

$ErrorActionPreference = 'Stop'

Write-Host "Installing Native Messaging host for SERP Companion..." -ForegroundColor Cyan

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$runBat = Join-Path $scriptDir 'run-host.bat'
$manifestPath = Join-Path $scriptDir 'com.serp.companion.json'

if (-not (Test-Path $runBat)) {
  throw "run-host.bat not found at $runBat"
}

if (-not $ExtensionId) {
  $ExtensionId = Read-Host 'Enter your Chrome Extension ID (from chrome://extensions)'
}

$manifest = @{
  name = 'com.serp.companion'
  description = 'SERP Companion Native Host'
  path = (Resolve-Path $runBat).Path
  type = 'stdio'
  allowed_origins = @("chrome-extension://$ExtensionId/")
}

$json = $manifest | ConvertTo-Json -Depth 5
Set-Content -LiteralPath $manifestPath -Value $json -Encoding UTF8
Write-Host "Wrote manifest to $manifestPath" -ForegroundColor Green

$regKey = 'HKCU\Software\Google\Chrome\NativeMessagingHosts\com.serp.companion'

Write-Host "Registering manifest in registry..." -ForegroundColor Cyan
& reg.exe ADD $regKey /ve /t REG_SZ /d "$manifestPath" /f | Out-Null

Write-Host "Done. Restart Chrome if it was open." -ForegroundColor Green

