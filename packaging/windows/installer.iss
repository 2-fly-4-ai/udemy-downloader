; Inno Setup script for SERP Companion (Udemy Helper)
; Build with Inno Setup Compiler (https://jrsoftware.org/)

#define MyAppName "SERP Companion"
#define MyAppVersion "0.1.1"
#define MyAppPublisher "Your Company"
#define MyAppExeName "serp-companion.exe"
; Extension ID from Chrome Web Store (stable ID). For dev, set your unpacked ID.
#define MyExtensionId "kjeahghmchmcjnmhmbmlfcgkhjmkcpie"
; Optional: Chrome Web Store slug for your extension page (improves URL). Example: "serp-companion-udemy-helper"
#define MyExtensionSlug "your_extension_slug_here"

[Setup]
AppId={{1C0E6B5E-1A49-4B8E-8C94-3D2B6B1E1234}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\SERP Companion
DefaultGroupName=SERP Companion
OutputBaseFilename=SERP-Companion-Setup
; Emit installer EXE to repo-root dist-installer\
OutputDir=..\..\dist-installer
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; Binaries built by PyInstaller (located in repo root bin\)
Source: "..\..\bin\serp-companion.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "..\..\bin\udemy-downloader.exe"; DestDir: "{app}\bin"; Flags: ignoreversion

; Bundled tools (located in repo root tools\) — optional wildcard
Source: "..\..\tools\*"; DestDir: "{app}\tools"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
; Explicit common tool binaries (included if present)
Source: "..\..\tools\ffmpeg.exe"; DestDir: "{app}\tools"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\..\tools\ffprobe.exe"; DestDir: "{app}\tools"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\..\tools\shaka-packager.exe"; DestDir: "{app}\tools"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\..\tools\yt-dlp.exe"; DestDir: "{app}\tools"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\..\tools\aria2c.exe"; DestDir: "{app}\tools"; Flags: ignoreversion skipifsourcedoesntexist
; Include repo's aria2c.exe by default (root) as final fallback
Source: "..\..\aria2c.exe"; DestDir: "{app}\tools"; Flags: ignoreversion skipifsourcedoesntexist

; Optional: default keyfile placeholder (root)
Source: "..\..\keyfile.json"; DestDir: "{app}"; Flags: onlyifdoesntexist skipifsourcedoesntexist

[Icons]
Name: "{group}\SERP Companion"; Filename: "{app}\bin\{#MyAppExeName}"
Name: "{autodesktop}\SERP Companion"; Filename: "{app}\bin\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Start the pairing server so the extension can self-register by clicking "Pair Desktop"
Filename: "{app}\\bin\\{#MyAppExeName}"; Parameters: "--pair-server"; Flags: nowait postinstall skipifsilent
; Open the specific extension page if slug is configured; otherwise open the store home
#if "{#MyExtensionSlug}" != "your_extension_slug_here"
Filename: "{cmd}"; Parameters: "/C start https://chrome.google.com/webstore/detail/{#MyExtensionSlug}/{#MyExtensionId}"; Description: "Open Extension Page"; Flags: nowait postinstall skipifsilent
#else
Filename: "{cmd}"; Parameters: "/C start https://chrome.google.com/webstore/category/extensions"; Description: "Open Chrome Web Store"; Flags: nowait postinstall skipifsilent
#endif

[Registry]
; Register Chrome Native Messaging host (per-user)
Root: HKCU; Subkey: "Software\Google\Chrome\NativeMessagingHosts\com.serp.companion"; ValueType: string; ValueData: "{app}\\com.serp.companion.json"; Flags: uninsdeletekeyifempty

[Code]
function GenerateManifest(InstallPath: String): String;
var
  Manifest: String;
begin
  Manifest := '{"name":"com.serp.companion","description":"SERP Companion Native Host","path":"' + InstallPath + '\\bin\\' + '{#MyAppExeName}' + '","type":"stdio","allowed_origins":["chrome-extension://{#MyExtensionId}/"]}';
  Result := Manifest;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ManifestPath: String;
  Manifest: String;
  Wrote: Boolean;
begin
  if CurStep = ssPostInstall then
  begin
    ManifestPath := ExpandConstant('{app}') + '\\com.serp.companion.json';
    Manifest := GenerateManifest(ExpandConstant('{app}'));
    if FileExists(ManifestPath) then DeleteFile(ManifestPath);
    Wrote := SaveStringToFile(ManifestPath, Manifest, False);
    if not Wrote then
    begin
      Log('Failed to write manifest: ' + ManifestPath);
    end;
  end;
end;
