; Inno Setup script for the JithuBrowser Windows installer.
; Build:  ISCC /DAppVersion=155.0.8059.39.1 /DSourceDir=... /DOutputDir=... /DIconFile=... jithubrowser.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F1B2E8C-3D7A-4B53-9A41-JITHUBROWSER01}
AppName=JithuBrowser
AppVersion={#AppVersion}
AppPublisher=Jitheswar
AppPublisherURL=https://github.com/Jitheswar/JithuBrowser
AppSupportURL=https://github.com/Jitheswar/JithuBrowser/issues
DefaultDirName={autopf}\JithuBrowser
DefaultGroupName=JithuBrowser
UninstallDisplayIcon={app}\jithubrowser.exe
SetupIconFile={#IconFile}
OutputDir={#OutputDir}
OutputBaseFilename=JithuBrowser-{#AppVersion}-windows-x64-installer
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
LicenseFile={#SourceDir}\LICENSE.JithuBrowser

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\JithuBrowser"; Filename: "{app}\jithubrowser.exe"
Name: "{autodesktop}\JithuBrowser"; Filename: "{app}\jithubrowser.exe"; Tasks: desktopicon

[Registry]
; Offer JithuBrowser in Windows "Default apps"
Root: HKA; Subkey: "Software\Clients\StartMenuInternet\JithuBrowser\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "JithuBrowser"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Clients\StartMenuInternet\JithuBrowser\Capabilities\URLAssociations"; ValueType: string; ValueName: "http"; ValueData: "JithuBrowserHTML"
Root: HKA; Subkey: "Software\Clients\StartMenuInternet\JithuBrowser\Capabilities\URLAssociations"; ValueType: string; ValueName: "https"; ValueData: "JithuBrowserHTML"
Root: HKA; Subkey: "Software\Classes\JithuBrowserHTML\shell\open\command"; ValueType: string; ValueData: """{app}\jithubrowser.exe"" ""%1"""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "JithuBrowser"; ValueData: "Software\Clients\StartMenuInternet\JithuBrowser\Capabilities"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\jithubrowser.exe"; Description: "Launch JithuBrowser"; Flags: nowait postinstall skipifsilent
