; Build through build.py so paths and version come from the checked-out source.
#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef BundleDir
  #error BundleDir is required
#endif
#ifndef OutputDir
  #error OutputDir is required
#endif
#ifndef RepoDir
  #error RepoDir is required
#endif

[Setup]
AppId={{9D58FAD0-FA8F-47EC-A526-028E4EA94201}
AppName=Capri
AppVersion={#AppVersion}
AppPublisher=Capri contributors
AppPublisherURL=https://github.com/Capri-cmd/capri-ai
DefaultDirName={localappdata}\Programs\Capri
DefaultGroupName=Capri
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=Capri-Setup
SetupIconFile={#BundleDir}\capri.ico
UninstallDisplayIcon={app}\Capri.exe
LicenseFile={#RepoDir}\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Capri"; Filename: "{app}\Capri.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Capri"; Filename: "{app}\Capri.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Capri.exe"; Description: "Start Capri (download a brain and ears from her right-click menu)"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

; config.yaml, data/, models/ and engines/ are created by Capri, never installed
; or deleted here. Upgrades and uninstall preserve them.
