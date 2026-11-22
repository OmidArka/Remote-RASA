[Setup]
AppName=RasaDesk
AppVersion=0.5.0
AppPublisher=Amn Negar Rasa
DefaultDirName={autopf}\RasaDesk
DefaultGroupName=RasaDesk
OutputDir=installer
OutputBaseFilename=RasaDesk-Setup
SetupIconFile=rasadesk.ico
UninstallDisplayIcon={app}\RasaDesk.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"
Name: "startup"; Description: "Start RasaDesk with Windows (all users)"

[Files]
Source: "dist\RasaDesk\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\RasaDesk"; Filename: "{app}\RasaDesk.exe"
Name: "{autodesktop}\RasaDesk"; Filename: "{app}\RasaDesk.exe"; Tasks: desktopicon
Name: "{commonstartup}\RasaDesk"; Filename: "{app}\RasaDesk.exe"; Tasks: startup

[Run]
Filename: "{sys}\sc.exe"; Parameters: "start RasaDeskService"; Flags: runhidden; StatusMsg: "Starting RasaDesk service (if installed)..."
Filename: "{app}\RasaDesk.exe"; Description: "Launch RasaDesk"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\RasaDesk.exe"; Parameters: "--svc-uninstall"; Flags: runhidden; RunOnceId: "RasaDeskRemoveService"

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var rc: Integer;
begin
  { stop a previously installed service so its files can be replaced }
  Exec(ExpandConstant('{sys}\sc.exe'), 'stop RasaDeskService', '', SW_HIDE, ewWaitUntilTerminated, rc);
  Sleep(2500);
  Result := '';
end;
