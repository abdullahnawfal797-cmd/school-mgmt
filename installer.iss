; Script generated for Madrasati School Management System
#define MyAppName "نظام مدرستي للإدارة المدرسية"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "منظومة الإدارة المدرسية الحديثة"
#define MyAppExeName "Madrasati.exe"

[Setup]
AppId={{E8B62A4D-798B-4B35-901B-94EFA9CD1045}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Madrasati
DefaultGroupName={#MyAppName}
OutputDir=.
OutputBaseFilename=Madrasati_Setup_v1.0
SetupIconFile=app_icon.ico
LicenseFile=license.txt
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Dirs]
Name: "{app}"; Permissions: users-full

[Files]
Source: "dist\Madrasati\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Madrasati\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "db.sqlite3"
Source: "dist\Madrasati\db.sqlite3"; DestDir: "{app}"; Flags: ignoreversion uninsneveruninstall

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon; IconFilename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent