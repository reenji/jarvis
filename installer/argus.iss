; Inno Setup 6 script for the ARGUS Windows installer.
; Build after PyInstaller has produced dist\ARGUS:
;   iscc /DAppVersion=0.3.0 installer\argus.iss
; Output: dist\ARGUS-windows-x64-setup.exe (unversioned, so
; releases/latest/download/ links stay valid across releases)
;
; Installs per user (no administrator prompt) so the app can keep writing
; config\, memory\ and outputs\ beside its executables. Upgrades replace only
; the shipped files; the user's keys and memory stay in place, also on
; uninstall.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6B0E8E52-3C1A-4F0B-9B7A-2F4C1D9A7E31}
AppName=Argus
AppVersion={#AppVersion}
AppVerName=Argus {#AppVersion}
AppPublisher=reenji
AppPublisherURL=https://github.com/reenji/jarvis
DefaultDirName={autopf}\Argus
DefaultGroupName=Argus
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesEnvironment=yes
SetupIconFile=..\assets\argus.ico
UninstallDisplayIcon={app}\ARGUS.exe
OutputDir=..\dist
OutputBaseFilename=ARGUS-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
brazilianportuguese.AddToPath=Usar o comando argus no terminal (adiciona ao PATH)
english.AddToPath=Use the argus command in a terminal (adds it to PATH)
brazilianportuguese.TerminalShortcut=Argus Terminal
english.TerminalShortcut=Argus Terminal

[Tasks]
Name: "addtopath"; Description: "{cm:AddToPath}"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\ARGUS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Argus"; Filename: "{app}\ARGUS.exe"
Name: "{autoprograms}\{cm:TerminalShortcut}"; Filename: "{app}\argus.com"; Parameters: "chat"; IconFilename: "{app}\ARGUS.exe"
Name: "{autodesktop}\Argus"; Filename: "{app}\ARGUS.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NeedsAddPath(ExpandConstant('{app}'))

[Run]
Filename: "{app}\ARGUS.exe"; Description: "{cm:LaunchProgram,Argus}"; Flags: nowait postinstall skipifsilent

[Code]
function PathContains(Paths, Dir: string): Boolean;
begin
  Result := Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(Paths) + ';') > 0;
end;

function NeedsAddPath(Dir: string): Boolean;
var
  Paths: string;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', Paths) then
    Paths := '';
  Result := not PathContains(Paths, Dir);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Paths, Dir: string;
  Index: Integer;
begin
  if CurUninstallStep <> usPostUninstall then
    exit;
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', Paths) then
    exit;
  Dir := ExpandConstant('{app}');
  Paths := ';' + Paths + ';';
  Index := Pos(';' + Uppercase(Dir) + ';', Uppercase(Paths));
  if Index = 0 then
    exit;
  Delete(Paths, Index, Length(Dir) + 1);
  Paths := Copy(Paths, 2, Length(Paths) - 2);
  RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Paths);
end;
