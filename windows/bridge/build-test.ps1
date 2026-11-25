# INTERNER, UNSIGNIERTER, UNQUALIFIZIERTER Testbuild der GUI "GSVmulti-Bruecke".
# Kein freigegebener Bauweg (der bleibt build.ps1 + packaging/bridge.spec mit
# Hash-Locks und Qualifikation). Nur Windows 11 x64, Python >=3.13 x64 explizit.
#   .\windows\bridge\build-test.ps1 -Python 'C:\Python313\python.exe' [-Inno 'C:\...\ISCC.exe']
# Bequem: Doppelklick auf build-test.cmd (Ausfuehrungsrichtlinie nur fuer diesen Lauf umgangen, Python 3.13 gefunden).
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Python,
    [string]$Inno,
    [string]$OutputDirectory = "",
    [switch]$Release   # Release-Build (build-release.cmd): saubere Version, Kanal "Release", dist-release; verweigert bei geaendertem Arbeitsbaum
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    # pip liest sonst maschinenweite Konfiguration (Extra-Index, trusted-host).
    $Previous = [Environment]::GetEnvironmentVariable("PIP_CONFIG_FILE", "Process")
    try {
        $env:PIP_CONFIG_FILE = "NUL"
        & $Program @Arguments
        if ($LASTEXITCODE -ne 0) { throw "Befehl fehlgeschlagen (Exit $LASTEXITCODE): $Program $($Arguments -join ' ')" }
    }
    finally {
        if ($null -eq $Previous) { Remove-Item Env:PIP_CONFIG_FILE -ErrorAction SilentlyContinue }
        else { $env:PIP_CONFIG_FILE = $Previous }
    }
}

function Test-BuiltExe {
    param([string]$Exe, [string]$SelfTestJson)
    if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) { throw "EXE nicht erzeugt: $Exe" }
    $Proc = Start-Process -FilePath $Exe -ArgumentList @("--self-test-out", "`"$SelfTestJson`"") -PassThru -WindowStyle Hidden
    try {
        if (-not $Proc.WaitForExit(120000)) { $Proc.Kill(); throw "Selbsttest: Zeitueberschreitung bei $Exe" }
        if (-not (Test-Path -LiteralPath $SelfTestJson -PathType Leaf)) {
            throw "Selbsttest hat kein Ergebnis geschrieben (Exit $($Proc.ExitCode)): $Exe"
        }
        $Raw = Get-Content -LiteralPath $SelfTestJson -Raw -Encoding UTF8
        $Report = $Raw | ConvertFrom-Json
        if ($Proc.ExitCode -ne 0 -or -not $Report.ok -or -not $Report.frozen) {
            Write-Output $Raw
            throw "Selbsttest der EXE fehlgeschlagen: $Exe"
        }
        Write-Output "Selbsttest bestanden: $Exe"
    }
    finally {
        $Proc.Dispose()
    }
}

if ($env:OS -ne "Windows_NT") { throw "Build gesperrt: nur auf Windows 11 x64 moeglich (PyInstaller baut nur fuer das Host-System)." }
if (-not [Environment]::Is64BitOperatingSystem) { throw "Build gesperrt: 64-Bit-Windows erforderlich." }
if ([Environment]::OSVersion.Version.Build -lt 22000) { throw "Build gesperrt: Windows 11 (Build >= 22000) erforderlich." }

# Kein Suchen im PATH: der Interpreter wird ausdruecklich angegeben.
$Python = (Resolve-Path -LiteralPath $Python).Path
Invoke-Checked $Python @("-I", "-c", "import sys,struct; sys.exit(0 if sys.version_info >= (3,13) and struct.calcsize('P') == 8 and sys.platform == 'win32' else 'Python >=3.13 x64 fuer Windows erforderlich.')")
if ($Inno) {
    if (-not (Test-Path -LiteralPath $Inno -PathType Leaf)) { throw "ISCC.exe nicht gefunden: $Inno" }
    $Inno = (Resolve-Path -LiteralPath $Inno).Path
}
else {
    $Candidates = @(
        if (${env:ProgramFiles(x86)}) { Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6/ISCC.exe" }
        if ($env:ProgramFiles) { Join-Path $env:ProgramFiles "Inno Setup 6/ISCC.exe" }
        if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA "Programs/Inno Setup 6/ISCC.exe" }
    )
    foreach ($Candidate in $Candidates) {
        if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
            $Inno = $Candidate
            break
        }
    }
}
if (-not $Inno) {
    $InnoHint = "ISCC.exe fehlt. Inno Setup installieren: winget install JRSoftware.InnoSetup"
    if ($Release) { throw "Release-Build gesperrt: $InnoHint" }
    Write-Warning "$InnoHint. Dieser Testbuild erzeugt nur die portable EXE."
}

# $PSScriptRoot ist in Windows PowerShell 5.1 in Parametervorgaben leer;
# deshalb erst hier auswerten, mit Rueckfall auf den Skriptpfad.
$BridgeRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $BridgeRoot $(if ($Release) { "dist-release" } else { "dist-test" }) }
$RepoRoot = (Resolve-Path (Join-Path $BridgeRoot "../..")).Path
$Version = ([regex]::Match((Get-Content -LiteralPath (Join-Path $BridgeRoot "pyproject.toml") -Raw), '(?m)^version\s*=\s*"([^"]+)"')).Groups[1].Value
if (-not $Version) { throw "Version in pyproject.toml nicht gefunden." }

$Commit = "unbekannt"
$Dirty = $false
# Ohne Git (z. B. ZIP-Download) bleibt die Quelle "unbekannt"; der Bau laeuft trotzdem.
if (Test-Path -LiteralPath (Join-Path $RepoRoot ".git")) {
    try {
        $Head = (& git -C $RepoRoot rev-parse HEAD 2>$null)
        if ($LASTEXITCODE -eq 0 -and $Head) {
            $Commit = $Head.Trim()
            $Dirty = [bool](& git -C $RepoRoot status --porcelain --untracked-files=no 2>$null)
        }
    } catch { $Commit = "unbekannt" }
}
$Commit12 = if ($Commit.Length -ge 12) { $Commit.Substring(0, 12) } else { $Commit }
$CommitLabel = if ($Dirty) { "$Commit+geaendert" } else { $Commit }
if ($Release) {
    if ($Commit -eq "unbekannt") { throw "Release-Build gesperrt: Git-Commit nicht ermittelbar (Quelle muss ein Git-Arbeitsbaum sein)." }
    if ($Dirty) { throw "Release-Build gesperrt: der Arbeitsbaum hat nicht eingecheckte Aenderungen. Erst committen, dann bauen." }
}

$BuildId = [Guid]::NewGuid().ToString("N").Substring(0, 12)
$BuildRoot = Join-Path $BridgeRoot ".build-test/$BuildId"
$Venv = Join-Path $BuildRoot "venv"
$VenvPython = Join-Path $Venv "Scripts/python.exe"
$DistPath = Join-Path $BuildRoot "dist"
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
$BuildInfo = Join-Path $BridgeRoot "src/dispread_bridge_app/build_info.py"
$Channel = if ($Release) { "Release" } else { "Interner Testbuild - nicht qualifiziert" }
$Suffix = if ($Release) { "" } else { "-$Commit12-test" }
$PackageName = "GSVmulti-Bruecke-$Version$Suffix"

New-Item -ItemType Directory -Path $BuildRoot, $OutputDirectory -Force | Out-Null
if ($Release) { Write-Output "== RELEASE-BUILD $Version (Commit $Commit12) ==" }
else { Write-Output "== INTERNER TESTBUILD: unsigniert, unqualifiziert, nur interner Test ==" }

Invoke-Checked $Python @("-I", "-m", "venv", $Venv)
Invoke-Checked $VenvPython @("-I", "-m", "pip", "--isolated", "install", "--index-url", "https://pypi.org/simple",
    "--only-binary=:all:", "-r", (Join-Path $BridgeRoot "requirements-runtime.in"), "pyinstaller")

$Info = @"
version = "$Version"
commit = "$CommitLabel"
build_time_utc = "$([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))"
channel = "$Channel"
"@
[System.IO.File]::WriteAllText($BuildInfo, $Info, (New-Object System.Text.UTF8Encoding($false)))
try {
    $Spec = Join-Path $BridgeRoot "packaging/bridge-app.spec"
    $BuildArgs = @("-I", "-m", "PyInstaller", "--clean", "--noconfirm", "--distpath", $DistPath)
    Invoke-Checked $VenvPython ($BuildArgs + @("--workpath", (Join-Path $BuildRoot "pyinstaller-portable"),
        $Spec, "--", "--portable"))
    if ($Inno) {
        Invoke-Checked $VenvPython ($BuildArgs + @("--workpath", (Join-Path $BuildRoot "pyinstaller-onedir"), $Spec))
    }
}
finally {
    Remove-Item -LiteralPath $BuildInfo -ErrorAction SilentlyContinue
}

$PortableExe = Join-Path $DistPath "GSVmulti-Bruecke.exe"
Test-BuiltExe $PortableExe (Join-Path $BuildRoot "selftest-portable.json")
$Artifacts = [ordered]@{ "$PackageName-portable.exe" = $PortableExe }

# Setup: beim Release Pflicht, beim Testbuild optional.
if ($Inno) {
    $AppDir = Join-Path $DistPath "GSVmulti-Bruecke"
    $OnedirExe = Join-Path $AppDir "GSVmulti-Bruecke.exe"
    Test-BuiltExe $OnedirExe (Join-Path $BuildRoot "selftest-onedir.json")
    $SetupOut = Join-Path $BuildRoot "setup"
    New-Item -ItemType Directory -Path $SetupOut -Force | Out-Null
    $IsccArgs = @("/DAppDir=$AppDir", "/DAppVersion=$Version", "/DAppCommit=$Commit12", "/DSetupOutput=$SetupOut")
    if ($Release) { $IsccArgs += "/DRelease=1" }
    Invoke-Checked $Inno ($IsccArgs + (Join-Path $BridgeRoot "packaging/setup-app.iss"))
    $SetupName = "GSVmulti-Bruecke-Setup-$Version$Suffix.exe"
    $SetupBuilt = Join-Path $SetupOut $SetupName
    if (-not (Test-Path -LiteralPath $SetupBuilt -PathType Leaf)) { throw "Setup nicht erzeugt." }
    $Artifacts[$SetupName] = $SetupBuilt
}
$SumsFile = Join-Path $OutputDirectory "$PackageName-SHA256SUMS.txt"
if (Test-Path -LiteralPath $SumsFile) { throw "Ausgabe existiert bereits: $SumsFile" }
$Sums = foreach ($Name in $Artifacts.Keys) {
    $Target = Join-Path $OutputDirectory $Name
    if (Test-Path -LiteralPath $Target) { throw "Ausgabe existiert bereits: $Target" }
    $Hash = (Get-FileHash -LiteralPath $Artifacts[$Name] -Algorithm SHA256).Hash.ToLowerInvariant()
    "$Hash  $Name"
}
foreach ($Name in $Artifacts.Keys) {
    $Target = Join-Path $OutputDirectory $Name
    Move-Item -LiteralPath $Artifacts[$Name] -Destination $Target
    Write-Output $Target
}
Set-Content -LiteralPath $SumsFile -Value $Sums -Encoding ASCII
Write-Output "Quelle: $CommitLabel  Version: $Version"
if ($Release) { Write-Output "Release $Version gebaut (unsigniert). Fuer Forgejo: portable EXE, Setup und $PackageName-SHA256SUMS.txt aus $OutputDirectory." }
else { Write-Output "Unsigniert, unqualifiziert, nur interner Test. Kein Ersatz fuer build.ps1; keine Windows-Abnahme (N1/N2/N3)." }
