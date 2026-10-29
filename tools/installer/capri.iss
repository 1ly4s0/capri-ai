; Capri-Setup.exe: the classic Windows setup wizard. Built by tools/build_release.py, which defines AppDir (the
; PyInstaller build), Version, Media and Out, and writes generated.iss (the components and their downloads, from
; capri/portable.py's lists).

#define AppName "Capri"

[Setup]
AppId={{6F3C2A77-CA9B-4E2D-9C1A-CAPRI0000001}
AppName={#AppName}
AppVersion={#Version}
AppVerName={#AppName} {#Version}
AppPublisher=Capri (fan-made)
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=classic
WizardImageFile={#Media}\side-100.bmp,{#Media}\side-125.bmp,{#Media}\side-150.bmp,{#Media}\side-175.bmp,{#Media}\side-200.bmp,{#Media}\side-225.bmp,{#Media}\side-250.bmp
WizardSmallImageFile={#Media}\corner-100.bmp,{#Media}\corner-125.bmp,{#Media}\corner-150.bmp,{#Media}\corner-175.bmp,{#Media}\corner-200.bmp,{#Media}\corner-225.bmp,{#Media}\corner-250.bmp
SetupIconFile={#Media}\capri.ico
UninstallDisplayIcon={app}\Capri.exe
UninstallDisplayName={#AppName}
LicenseFile={#Media}\..\LICENSE.txt
OutputDir={#Out}
OutputBaseFilename=Capri-Setup
Compression=lzma2/normal
SolidCompression=yes
ArchiveExtraction=full
DisableWelcomePage=no
DisableDirPage=no
DisableProgramGroupPage=yes
CloseApplications=yes

[Messages]
WelcomeLabel2=This will install [name/ver] on your computer.%n%nCapri is a desktop companion from Cyberpunk: Edgerunners 2 (fan-made): she roams your screen, sits on your windows, talks with you, sees your screen when you ask and does little jobs on your PC.%n%nNext you'll pick what she gets: her brain, her ears and her voice. Everything runs on your PC.
SelectComponentsLabel2=Pick what Capri gets. The big parts download while she installs, straight into her folder.
FinishedLabel=Capri is installed. Start her below and she'll drop onto your desktop.%n%nClick her to type, hold Ctrl+1 to talk, right-click her for everything else.

[Types]
Name: "full"; Description: "Everything (recommended)"
Name: "light"; Description: "Light: smaller brain, smaller ears"
Name: "custom"; Description: "Custom: pick it yourself"; Flags: iscustom

[Components]
Name: "app"; Description: "Capri"; Types: full light custom; Flags: fixed
#include "generated-components.iss"

[Tasks]
Name: "eyes"; Description: "Let her look at your screen when you ask her to (her eyes)"; GroupDescription: "Capri:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "{#AppDir}\*"; DestDir: "{app}"; Excludes: "config.yaml"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#AppDir}\config.yaml"; DestDir: "{app}"; Flags: onlyifdoesntexist
Source: "{#Media}\night-drive.mp3"; Flags: dontcopy
#include "generated-files.iss"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\Capri.exe"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\Capri.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Capri.exe"; Parameters: "--installed {code:PickedArgs}"; StatusMsg: "Setting Capri up..."; Flags: runhidden waituntilterminated
Filename: "{app}\Capri.exe"; Description: "Start Capri"; Flags: postinstall nowait skipifsilent
Filename: "{app}\README.txt"; Description: "Open the README"; Flags: postinstall shellexec skipifsilent unchecked

[UninstallDelete]
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{app}\models"
Type: filesandordirs; Name: "{app}\engines"

[Code]
function mciSendString(Command: String; ReturnString: Integer; ReturnLength: Cardinal; Callback: HWND): Cardinal;
  external 'mciSendStringW@winmm.dll stdcall';

var
  NamePage: TInputQueryWizardPage;
  MusicButton: TNewButton;
  MusicOn: Boolean;
  EngineChosen: Boolean;

#include "generated-code.iss"

procedure MusicClick(Sender: TObject);
begin
  MusicOn := not MusicOn;
  if MusicOn then begin
    mciSendString('resume bgm', 0, 0, 0);
    MusicButton.Caption := 'Music: on';
  end else begin
    mciSendString('pause bgm', 0, 0, 0);
    MusicButton.Caption := 'Music: off';
  end;
end;

procedure InitializeWizard;
begin
  NamePage := CreateInputQueryPage(wpSelectComponents, 'About you', 'What should Capri call you?',
    'She uses this name when she talks to you. You can change it any time in config.yaml.');
  NamePage.Add('Your name:', False);

  { the setup music: "Night Drive", on loop, with a button to turn it off. Never in a silent install: no window,
    so nothing to mute it with }
  if WizardSilent then Exit;
  ExtractTemporaryFile('night-drive.mp3');
  mciSendString('open "' + ExpandConstant('{tmp}\night-drive.mp3') + '" type mpegvideo alias bgm', 0, 0, 0);
  mciSendString('setaudio bgm volume to 450', 0, 0, 0);
  mciSendString('play bgm repeat', 0, 0, 0);
  MusicOn := True;
  MusicButton := TNewButton.Create(WizardForm);
  MusicButton.Parent := WizardForm;
  MusicButton.Left := ScaleX(10);
  MusicButton.Top := WizardForm.CancelButton.Top;
  MusicButton.Width := ScaleX(90);
  MusicButton.Height := WizardForm.CancelButton.Height;
  MusicButton.Caption := 'Music: on';
  MusicButton.OnClick := @MusicClick;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  { NVIDIA card: run her brain on CUDA, else Vulkan (any GPU). Only the first time the page shows. }
  if (CurPageID = wpSelectComponents) and not EngineChosen then begin
    EngineChosen := True;
    if FileExists(ExpandConstant('{sys}\nvidia-smi.exe')) then
      WizardSelectComponents('brain\engine\cuda,!brain\engine\vulkan')
    else
      WizardSelectComponents('brain\engine\vulkan,!brain\engine\cuda');
  end;
end;

function Quoted(S: String): String;
begin
  StringChangeEx(S, '"', '', True);
  Result := '"' + S + '"';
end;

function PickedArgs(Param: String): String;
begin
  Result := PickedComponents();
  if WizardIsComponentSelected('voice') then Result := Result + ' voice=1' else Result := Result + ' voice=0';
  if WizardIsTaskSelected('eyes') then Result := Result + ' eyes=1' else Result := Result + ' eyes=0';
  if Trim(NamePage.Values[0]) <> '' then Result := Result + ' ' + Quoted('name=' + Trim(NamePage.Values[0]));
end;

function Missing(Path: String): Boolean;
begin
  Result := not FileExists(ExpandConstant(Path));
end;

procedure DeinitializeSetup();
begin
  mciSendString('close bgm', 0, 0, 0);
end;
