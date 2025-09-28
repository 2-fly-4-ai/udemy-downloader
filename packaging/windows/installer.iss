; Inno Setup script for SERP Companion (Udemy Helper)
; Build with Inno Setup Compiler (https://jrsoftware.org/)

#define MyAppName "SERP Companion"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Your Company"
#define MyAppExeName "serp-companion.exe"
; Extension ID from Chrome Web Store (stable ID). For dev, set your unpacked ID.
#define MyExtensionId "your_extension_id_here"
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
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; Binaries built by PyInstaller
Source: "bin\serp-companion.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "bin\udemy-downloader.exe"; DestDir: "{app}\bin"; Flags: ignoreversion

; Bundled tools (place your files here before building the installer)
Source: "tools\*"; DestDir: "{app}\tools"; Flags: ignoreversion recursesubdirs createallsubdirs
; Include repo's aria2c.exe by default
Source: "aria2c.exe"; DestDir: "{app}\tools"; Flags: ignoreversion

; Optional: default keyfile placeholder
Source: "keyfile.json"; DestDir: "{app}"; Flags: onlyifdoesntexist

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
  F: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    ManifestPath := ExpandConstant('{app}') + '\\com.serp.companion.json';
    Manifest := GenerateManifest(ExpandConstant('{app}'));
    if FileExists(ManifestPath) then DeleteFile(ManifestPath);
    F := FileCreate(ManifestPath);
    if F <> -1 then
    begin
      FileWrite(F, Manifest[1], Length(Manifest));
      FileClose(F);
    end;
  end;
end;
