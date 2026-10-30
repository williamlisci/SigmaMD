#define MyAppName "SigmaMD"
#define MyAppVersion "1.0.4"
#define MyAppPublisher "SigmaMD"
#define MyAppExeName "SigmaMD.exe"
#define MyAppIcon "assets\SigmaMD.ico"

[Setup]
AppId=SigmaMD
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\SigmaMD
DefaultGroupName=SigmaMD
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=output
OutputBaseFilename=SigmaMD-Setup-1.0.4
SetupIconFile={#MyAppIcon}
ChangesAssociations=yes
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "fileassoc"; Description: "Register SigmaMD to open .md and .markdown files"; GroupDescription: "File associations:"

[Files]
Source: "dist\SigmaMD\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Registry]
; Register SigmaMD as an available handler for Markdown files for the current user.
; Windows 11 may still require the user to choose SigmaMD once in Default apps.
Root: HKCU; Subkey: "Software\Classes\SigmaMD.Markdown"; ValueType: string; ValueName: ""; ValueData: "Markdown Document"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\SigmaMD.Markdown\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\SigmaMD.exe,0"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\SigmaMD.Markdown\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\SigmaMD.exe"" ""%1"""; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.md\OpenWithProgids"; ValueType: none; ValueName: "SigmaMD.Markdown"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.markdown\OpenWithProgids"; ValueType: none; ValueName: "SigmaMD.Markdown"; Flags: uninsdeletevalue; Tasks: fileassoc

[Icons]
Name: "{autoprograms}\SigmaMD"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\SigmaMD"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch SigmaMD"; Flags: postinstall nowait skipifsilent
