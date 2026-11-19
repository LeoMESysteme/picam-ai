; Installer der GUI (ohne /DRelease: interner, unsignierter Test-Installer). Nur ueber build-test.ps1 / build-release.cmd.
; Benutzerinstallation ohne Administratorrechte. Kein Treiber, kein com0com, kein Autostart.
#ifndef AppDir
  #error AppDir muss den PyInstaller-Ordner nennen
#endif
#ifndef AppVersion
  #error AppVersion ist erforderlich
#endif
#ifndef AppCommit
  #error AppCommit ist erforderlich
#endif
#ifndef SetupOutput
  #error SetupOutput ist erforderlich
#endif
#if !FileExists(AppDir + "\GSVmulti-Bruecke.exe")
  #error GSVmulti-Bruecke.exe fehlt im Paket
#endif

[Setup]
AppId={{B3C2A3E1-5D0F-4C57-9E3A-6F1B2A7C4D18}
#ifdef Release
  AppName=GSVmulti-Bruecke
  AppVersion={#AppVersion}
  VersionInfoVersion={#AppVersion}.0
#else
  AppName=GSVmulti-Bruecke (interner Test)
  AppVersion={#AppVersion}-{#AppCommit}
  VersionInfoVersion=0.0.0.0
#endif
AppPublisher=ME Systeme
DefaultDirName={localappdata}\Programs\GSVmulti-Bruecke
DefaultGroupName=GSVmulti-Bruecke
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.22000
OutputDir={#SetupOutput}
#ifdef Release
  OutputBaseFilename=GSVmulti-Bruecke-Setup-{#AppVersion}
#else
  OutputBaseFilename=GSVmulti-Bruecke-Setup-{#AppVersion}-{#AppCommit}-test
#endif
Compression=lzma2
SolidCompression=yes
SignedUninstaller=no
#ifdef Release
  UninstallDisplayName=GSVmulti-Bruecke
#else
  UninstallDisplayName=GSVmulti-Bruecke (interner Test, unsigniert)
#endif
DisableProgramGroupPage=yes
ChangesAssociations=yes

[Files]
Source: "{#AppDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\GSVmulti-Bruecke"; Filename: "{app}\GSVmulti-Bruecke.exe"

; Dateizuordnung .dispread nur fuer den aktuellen Benutzer (HKCU).
[Registry]
Root: HKCU; Subkey: "Software\Classes\.dispread"; ValueType: string; ValueName: ""; ValueData: "GSVmulti-Bruecke.Profil"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\GSVmulti-Bruecke.Profil"; ValueType: string; ValueName: ""; ValueData: "GSVmulti-Bruecke Pi-Profil"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\GSVmulti-Bruecke.Profil\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\GSVmulti-Bruecke.exe"" ""%1"""

; Bewusst kein [UninstallDelete]: Benutzerdaten, Journale und Zugangsdaten
; (%LOCALAPPDATA%\dispread-bridge u. a.) gehoeren dem Benutzer, nicht dem Installer.
; Bewusst kein [Run]-Treiber, keine PATH-/Python-Aenderung, kein Autostart.
