#define AppName "WarDogs Tools"
#define AppVersion "1.0.2"
#define AppPublisher "WarDogs Tools"
#define AppExeName "WarDogsTools.exe"

[Setup]
AppId={{80E6A3B1-BC02-4D14-9761-5BC2E7B994C9}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\WarDogs Tools
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
SetupIconFile=assets\icon.ico
LicenseFile=installer\licenses\ViGEmBus-LICENSE.txt
OutputDir=dist
OutputBaseFilename=WarDogsTools-Setup
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "dist\WarDogsTools\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "installer\prerequisites\ViGEmBusSetup_x64.msi"; Flags: dontcopy
Source: "installer\licenses\ViGEmBus-LICENSE.txt"; DestDir: "{app}\licenses"; Flags: ignoreversion

[Icons]
Name: "{group}\WarDogs Tools"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\WarDogs Tools"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch WarDogs Tools"; Flags: postinstall nowait skipifsilent

[Code]
function IsViGEmBusInstalled: Boolean;
begin
  Result := RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\ViGEmBus');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  MsiPath: String;
begin
  Result := '';
  if IsViGEmBusInstalled then
    Exit;

  ExtractTemporaryFile('ViGEmBusSetup_x64.msi');
  MsiPath := ExpandConstant('{tmp}\ViGEmBusSetup_x64.msi');

  if not Exec(
    ExpandConstant('{sys}\msiexec.exe'),
    '/i "' + MsiPath + '" /passive /norestart',
    '',
    SW_SHOW,
    ewWaitUntilTerminated,
    ResultCode
  ) then
  begin
    Result := 'Could not start the ViGEmBus driver installer.';
    Exit;
  end;

  if (ResultCode = 3010) or (ResultCode = 1641) then
  begin
    NeedsRestart := True;
    Exit;
  end;

  if ResultCode <> 0 then
    Result := 'ViGEmBus installation failed (Windows Installer exit code ' +
      IntToStr(ResultCode) + ').';
end;
