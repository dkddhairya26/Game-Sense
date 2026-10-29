#ifdef GameSenseQA
  #define AppName "GameSense QA"
  #define AppIdentity "{{B246EE84-A56D-4BB0-9C35-851205C768D9}"
  #define AppFolder "GameSense-QA"
  #define InstallerFile "GameSenseSetup-Windows-QA"
#else
  #define AppName "GameSense"
  #define AppIdentity "{{6F0C5A20-41B6-4DB4-B5D9-A9BFA85A7201}"
  #define AppFolder "GameSense"
  #define InstallerFile "GameSenseSetup-Windows"
#endif
#define AppVersion "0.10.0"
[Setup]
AppId={#AppIdentity}
AppName={#AppName}
AppVersion={#AppVersion}
VersionInfoVersion=0.10.0.0
AppPublisher=GameSense
AppPublisherURL=https://github.com/dkddhairya26/Game-Sense
AppSupportURL=https://github.com/dkddhairya26/Game-Sense/issues
AppUpdatesURL=https://dkddhairya26.github.io/Game-Sense/
DefaultDirName={localappdata}\Programs\{#AppFolder}
DefaultGroupName={#AppName}
OutputDir=..\output
OutputBaseFilename={#InstallerFile}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\assets\gamesense.ico
UninstallDisplayIcon={app}\GameSense.exe
CloseApplications=yes
[Files]
Source: "..\dist\GameSense\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\GameSense.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\GameSense.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
[Run]
Filename: "{app}\GameSense.exe"; Description: "Launch GameSense"; Flags: nowait postinstall skipifsilent
