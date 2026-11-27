#define AppName "Control de impresión Accidental Maderas y Derivados"
#define AppPublisher "Corporación Tectronic S.A. de C.V."
#define AppEmail "soporte@tectronic.mx"
#define AppVersion "1.0.9"
#define AppExe "OccidentalMaderas.exe"

[Setup]
AppId={{108865B7-2A91-4915-ACD7-C9EF9380B703}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppContact={#AppEmail}
AppSupportURL=mailto:{#AppEmail}
DefaultDirName={localappdata}\Programs\Tectronic\Control de impresion Maderas
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
OutputDir=..\dist-installer
OutputBaseFilename=Control_Impresion_Accidental_Maderas_Setup
SetupIconFile=control-impresion.ico
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
VersionInfoVersion=1.0.9.0
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=Instalador de {#AppName}
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; Flags: unchecked

[Files]
Source: "..\dist-flet\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist-flet\catalogo-inicial.sqlite3"; DestDir: "{localappdata}\Occidental Maderas"; DestName: "etiquetas.sqlite3"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir {#AppName}"; Flags: nowait postinstall skipifsilent
