param(
  [switch]$Setup,
  [switch]$Build,
  [switch]$Installer,
  [switch]$HotReplace,
  [switch]$Pair,
  [switch]$Zip,
  [switch]$Release
)

$ErrorActionPreference = 'Stop'

function Resolve-RepoRoot {
  $scriptDir = $PSScriptRoot
  if (-not $scriptDir) { $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
  return Resolve-Path (Join-Path $scriptDir '..\..')
}

function Ensure-Venv {
  param([string]$RepoRoot)
  $venvPy = Join-Path $RepoRoot 'venv\Scripts\python.exe'
  if (-not (Test-Path $venvPy)) {
    Write-Host 'Creating venv and installing deps...' -ForegroundColor Cyan
    & python -m venv (Join-Path $RepoRoot 'venv')
  } else {
    Write-Host 'venv already exists.' -ForegroundColor DarkGray
  }
  & $venvPy -m pip install --upgrade pip | Out-Null
  & $venvPy -m pip install -r (Join-Path $RepoRoot 'requirements.txt') pyinstaller
}

function Build-Exes {
  param([string]$RepoRoot)
  $buildBat = Join-Path $RepoRoot 'packaging\windows\build.bat'
  if (-not (Test-Path $buildBat)) { throw 'build.bat not found' }
  Write-Host 'Building PyInstaller executables...' -ForegroundColor Cyan
  & $buildBat | Out-Host
  if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller build failed. Install PyInstaller and retry: venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller'
  }
}

function Find-InstallRoot {
  $paths = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\SERP Companion'),
    (Join-Path $env:ProgramFiles 'SERP Companion')
  )
  foreach ($p in $paths) { if (Test-Path $p) { return $p } }
  return $null
}

function HotReplace {
  param([string]$RepoRoot)
  $installRoot = Find-InstallRoot
  if (-not $installRoot) { throw 'Installed app not found. Run the installer first.' }
  $destBin = Join-Path $installRoot 'bin'
  $srcBin = Join-Path $RepoRoot 'bin'
  foreach ($name in 'serp-companion.exe','udemy-downloader.exe') {
    $src = Join-Path $srcBin $name
    if (Test-Path $src) {
      Write-Host "Copying $name -> $destBin" -ForegroundColor Cyan
      Copy-Item $src $destBin -Force
    } else {
      Write-Warning "Missing $src - did build succeed?"
    }
  }
}

function Build-Installer {
  param([string]$RepoRoot)
  $iss = Join-Path $RepoRoot 'packaging\windows\installer.iss'
  $isccPaths = @(
    'C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe',
    'C:\\Program Files\\Inno Setup 6\\ISCC.exe'
  )
  $iscc = $isccPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $iscc) { throw 'ISCC.exe not found. Install Inno Setup 6.' }
  Write-Host 'Compiling installer...' -ForegroundColor Cyan
  & $iscc $iss | Out-Host
}

function Ensure-Tools {
  param([string]$RepoRoot)
  $toolsDir = Join-Path $RepoRoot 'tools'
  if (-not (Test-Path $toolsDir)) {
    New-Item -ItemType Directory -Path $toolsDir | Out-Null
  }

  # Always ensure Shaka Packager is bundled so installs work out-of-the-box
  $shakaPath = Join-Path $toolsDir 'shaka-packager.exe'
  if (-not (Test-Path $shakaPath)) {
    Write-Host 'Fetching latest Shaka Packager for Windows (x64)...' -ForegroundColor Cyan
    try {
      # Some environments need explicit TLS 1.2
      try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }
      $release = Invoke-RestMethod -UseBasicParsing -Uri 'https://api.github.com/repos/shaka-project/shaka-packager/releases/latest'
      $asset = $release.assets | Where-Object { $_.name -eq 'packager-win-x64.exe' } | Select-Object -First 1
      if (-not $asset) { throw 'Could not find packager-win-x64.exe in latest release assets.' }
      $tmp = Join-Path $env:TEMP ('packager-win-x64_' + $release.tag_name + '.exe')
      Invoke-WebRequest -UseBasicParsing -Uri $asset.browser_download_url -OutFile $tmp
      Copy-Item $tmp $shakaPath -Force
      Remove-Item $tmp -Force
      Write-Host ("Placed: " + $shakaPath) -ForegroundColor Green
    } catch {
      throw "Failed to fetch Shaka Packager: $($_.Exception.Message)"
    }
  } else {
    Write-Host 'Shaka Packager already present in tools\' -ForegroundColor DarkGray
  }
}

function Start-PairServer {
  $installRoot = Find-InstallRoot
  if (-not $installRoot) { throw 'Installed app not found. Run the installer first.' }
  $exe = Join-Path $installRoot 'bin\serp-companion.exe'
  if (-not (Test-Path $exe)) { throw 'serp-companion.exe not found under install.' }
  Start-Process -FilePath $exe -ArgumentList '--pair-server' -WindowStyle Hidden
  Write-Host 'Pair server started at http://127.0.0.1:60123' -ForegroundColor Green
}

$repo = (Resolve-RepoRoot).Path

if ($Release) {
  $Setup = $true; $Build = $true; $Installer = $true; $Zip = $true
}

if (-not ($Setup -or $Build -or $Installer -or $HotReplace -or $Pair -or $Zip -or $Release)) {
  $Setup = $true; $Build = $true
}

if ($Setup) { Ensure-Venv -RepoRoot $repo }
if ($Build) { Build-Exes -RepoRoot $repo }
if ($HotReplace) { HotReplace -RepoRoot $repo }
if ($Installer) { Ensure-Tools -RepoRoot $repo; Build-Installer -RepoRoot $repo }
if ($Pair) { Start-PairServer }
if ($Zip) {
  $outDir = Join-Path $repo 'dist-installer'
  $exe = Join-Path $outDir 'SERP-Companion-Setup.exe'
  if (Test-Path $exe) {
    $zipPath = Join-Path $outDir 'SERP-Companion-Setup.zip'
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Write-Host 'Zipping installer...' -ForegroundColor Cyan
    Compress-Archive -Path $exe -DestinationPath $zipPath -Force
    Write-Host "Created: $zipPath" -ForegroundColor Green
  } else {
    Write-Warning "Installer not found at $exe - run with -Installer or -Release first."
  }
}

Write-Host 'Done.' -ForegroundColor Green
