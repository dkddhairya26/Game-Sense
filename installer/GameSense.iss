#define AppName "GameSense"
#define AppVersion "0.4.0"
[Setup]
AppId={{6F0C5A20-41B6-4DB4-B5D9-A9BFA85A7201}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\GameSense
DefaultGroupName=GameSense
OutputDir=..\output
OutputBaseFilename=GameSenseSetup-Windows
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
[Files]
Source: "..\dist\GameSense\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
[Icons]
Name: "{autoprograms}\GameSense"; Filename: "{app}\GameSense.exe"
Name: "{autodesktop}\GameSense"; Filename: "{app}\GameSense.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
[Run]
Filename: "{app}\GameSense.exe"; Description: "Launch GameSense"; Flags: nowait postinstall skipifsilent
