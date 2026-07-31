#define AppName "Đổi PDF sang Word (Băng Sơn)"
#define AppVersion "0.3.0"
#define AppExeName "Doi-PDF-sang-Word-Bang-Son.exe"

[Setup]
AppId={{B5CD846D-2D2D-4A27-9948-3D79E730758D}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Băng Sơn
DefaultDirName={autopf}\Doi PDF sang Word Bang Son
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist-installer
OutputBaseFilename=Setup-Doi-PDF-sang-Word-Bang-Son
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExeName}
PrivilegesRequired=lowest

[Files]
Source: "..\dist\Doi-PDF-sang-Word-Bang-Son\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng ngoài màn hình"; GroupDescription: "Biểu tượng bổ sung:"; Flags: unchecked

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Mở {#AppName}"; Flags: nowait postinstall skipifsilent
