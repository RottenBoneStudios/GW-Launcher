[Setup]
AppName=GW Launcher
AppVersion=1.0.0
DefaultDirName={pf}\GW Launcher
DefaultGroupName=GW Launcher
OutputBaseFilename=GWLauncher_Installer
Compression=lzma2
SolidCompression=yes

[Files]
Source: "dist\win-unpacked\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\GW Launcher"; Filename: "{app}\GW Launcher.exe"
Name: "{commondesktop}\GW Launcher"; Filename: "{app}\GW Launcher.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear icono en el escritorio"; GroupDescription: "Tareas adicionales:"

[Run]
Filename: "{app}\GW Launcher.exe"; Description: "Iniciar GW Launcher"; Flags: nowait postinstall skipifsilent
