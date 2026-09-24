; Inno Setup script for MigeCast IPTV (Windows 10/11 x64).
;
; Builds ONE public download: MigeCast-Setup-<version>.exe
;  * installs per user, no administrator rights: %LOCALAPPDATA%\Programs\MigeCast
;  * contains Python, Qt, libVLC + plugins and the MSVC runtime DLLs (app-local)
;  * Desktop and Start menu shortcuts
;  * upgrades in place (same AppId); user data in %LOCALAPPDATA%\MigeCast is
;    never touched by install, upgrade or uninstall
;
; Build:  ISCC.exe /DAppVersion=2.0.0 installer\MigeCast.iss
; Input:  dist\MigeCast\ (PyInstaller one-folder output)

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "MigeCast IPTV"
#define AppExe "MigeCast.exe"

[Setup]
; Never change AppId: it links upgrades and the uninstaller to earlier installs.
AppId={{6F1C6B2E-5C1B-4B8E-9E7A-4D5A3C2B1A90}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=MigeCast
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
DefaultDirName={localappdata}\Programs\MigeCast
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
DisableReadyPage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=Output
OutputBaseFilename=MigeCast-Setup-{#AppVersion}
SetupIconFile=..\resources\migecast.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=120
CloseApplications=yes
RestartApplications=no
ShowLanguageDialog=no
; Signing (optional): when a certificate is available, define SignTool in CI,
; e.g. /DSIGN=1 and configure "signtool" in the Inno Setup IDE/command line.
#ifdef SIGN
SignTool=signtool
SignedUninstaller=yes
#endif

[Languages]
#ifexist "SerbianLatin.isl"
Name: "sr"; MessagesFile: "SerbianLatin.isl"
#endif
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
#ifexist "SerbianLatin.isl"
sr.LaunchApp=Pokreni MigeCast IPTV
sr.DesktopIcon=Napravi prečicu na radnoj površini (Desktop)
#endif
en.LaunchApp=Start MigeCast IPTV
en.DesktopIcon=Create a desktop shortcut

[Tasks]
; Checked by default: older users expect the icon on the desktop.
Name: "desktopicon"; Description: "{cm:DesktopIcon}"

[InstallDelete]
; Remove files of the previous version before copying the new ones so no
; stale DLLs remain. User data is not inside {app}.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\MigeCast\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Only program files. %LOCALAPPDATA%\MigeCast (lists, favorites, history) stays,
; so reinstalling restores everything. See README "Removing all data".
Type: filesandordirs; Name: "{app}"
