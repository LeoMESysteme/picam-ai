; Internal, unsigned N1 runtime-probe qualification ONLY.
; No product GUI, privileged helper launcher, driver, Pi profile or release key.
; Compile only through build.ps1 after its existing N1 qualification gates.
#ifndef ProbePackage
  #error ProbePackage must name the qualified N1 package directory
#endif
#ifndef ProbeCommit
  #error ProbeCommit is required
#endif
#ifndef ProbeBuildId
  #error ProbeBuildId is required
#endif
#ifndef ProbeOutput
  #error ProbeOutput is required
#endif
#if !FileExists(ProbePackage + "\build-manifest.json")
  #error Qualified N1 package manifest is missing
#endif
#if !FileExists(ProbePackage + "\dispread-bridge-probe.exe")
  #error N1 runtime probe executable is missing
#endif

[Setup]
AppId={{7FF38BB8-CB7A-46D2-8108-70E122613B5E}
AppName=dispread internal runtime probe
AppVersion=internal-{#ProbeCommit}
VersionInfoVersion=0.0.0.0
AppPublisher=ME Systeme
DefaultDirName={autopf}\ME Systeme\dispread-bridge-internal-probe
PrivilegesRequired=admin
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.22000
OutputDir={#ProbeOutput}
OutputBaseFilename=internal-probe-setup-{#ProbeCommit}-{#ProbeBuildId}
Compression=lzma2
SolidCompression=yes
SignedUninstaller=no
UninstallDisplayName=dispread internal runtime probe (unsigned)
DisableProgramGroupPage=yes

[Files]
Source: "{#ProbePackage}\*"; DestDir: "{app}"; Excludes: "build-manifest.json"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ProbePackage}\build-manifest.json"; DestDir: "{app}"; Attribs: readonly; Flags: ignoreversion

; Deliberately no [Run], PATH/registry Python changes, autostart, or driver actions.
; Inno owns installed probe files only; user logs/config and port pairs are outside it.
