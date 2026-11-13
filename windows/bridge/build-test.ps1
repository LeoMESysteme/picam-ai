# INTERNER, UNSIGNIERTER, UNQUALIFIZIERTER Testbuild der GUI "GSVmulti-Bruecke".
# Kein freigegebener Bauweg (der bleibt build.ps1 + packaging/bridge.spec mit
# Hash-Locks und Qualifikation). Nur Windows 11 x64, Python >=3.13 x64 explizit.
#   .\windows\bridge\build-test.ps1 -Python 'C:\Python313\python.exe' [-Inno 'C:\...\ISCC.exe']
# Bequem: Doppelklick auf build-test.cmd (Ausfuehrungsrichtlinie nur fuer diesen Lauf umgangen, Python 3.13 gefunden).
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Python,
    [string]$Inno,
    [string]$OutputDirectory = ""
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

if ($env:OS -ne "Windows_NT") { throw "Build gesperrt: nur auf Windows 11 x64 moeglich (PyInstaller baut nur fuer das Host-System)." }
if (-not [Environment]::Is64BitOperatingSystem) { throw "Build gesperrt: 64-Bit-Windows erforderlich." }
if ([Environment]::OSVersion.Version.Build -lt 22000) { throw "Build gesperrt: Windows 11 (Build >= 22000) erforderlich." }

# Kein Suchen im PATH: der Interpreter wird ausdruecklich angegeben.
$Python = (Resolve-Path -LiteralPath $Python).Path
Invoke-Checked $Python @("-I", "-c", "import sys,struct; sys.exit(0 if sys.version_info >= (3,13) and struct.calcsize('P') == 8 and sys.platform == 'win32' else 'Python >=3.13 x64 fuer Windows erforderlich.')")
if ($Inno) { $Inno = (Resolve-Path -LiteralPath $Inno).Path }

# $PSScriptRoot ist in Windows PowerShell 5.1 in Parametervorgaben leer;
# deshalb erst hier auswerten, mit Rueckfall auf den Skriptpfad.
$BridgeRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $BridgeRoot "dist-test" }
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

$BuildId = [Guid]::NewGuid().ToString("N").Substring(0, 12)
$BuildRoot = Join-Path $BridgeRoot ".build-test/$BuildId"
$Venv = Join-Path $BuildRoot "venv"
$VenvPython = Join-Path $Venv "Scripts/python.exe"
$DistPath = Join-Path $BuildRoot "dist"
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
$BuildInfo = Join-Path $BridgeRoot "src/dispread_bridge_app/build_info.py"
$PackageName = "GSVmulti-Bruecke-$Version-$Commit12-test"

New-Item -ItemType Directory -Path $BuildRoot, $OutputDirectory -Force | Out-Null
Write-Output "== INTERNER TESTBUILD: unsigniert, unqualifiziert, nur interner Test =="

Invoke-Checked $Python @("-I", "-m", "venv", $Venv)
Invoke-Checked $VenvPython @("-I", "-m", "pip", "--isolated", "install", "--index-url", "https://pypi.org/simple",
    "--only-binary=:all:", "-r", (Join-Path $BridgeRoot "requirements-runtime.in"), "pyinstaller")

$Info = @"
version = "$Version"
commit = "$CommitLabel"
build_time_utc = "$([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))"
channel = "Interner Testbuild - nicht qualifiziert"
"@
[System.IO.File]::WriteAllText($BuildInfo, $Info, (New-Object System.Text.UTF8Encoding($false)))
try {
    Invoke-Checked $VenvPython @("-I", "-m", "PyInstaller", "--clean", "--noconfirm", "--distpath", $DistPath,
        "--workpath", (Join-Path $BuildRoot "pyinstaller"), (Join-Path $BridgeRoot "packaging/bridge-app.spec"))
}
finally {
    Remove-Item -LiteralPath $BuildInfo -ErrorAction SilentlyContinue
}

$AppDir = Join-Path $DistPath "GSVmulti-Bruecke"
$Exe = Join-Path $AppDir "GSVmulti-Bruecke.exe"
if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) { throw "EXE nicht erzeugt." }

# Selbsttest der gebauten EXE: ohne Fenster, Ergebnis als JSON-Datei (die EXE hat keine Konsole).
$SelfTestJson = Join-Path $BuildRoot "selftest.json"
$Proc = Start-Process -FilePath $Exe -ArgumentList @("--self-test-out", "`"$SelfTestJson`"") -PassThru -WindowStyle Hidden
if (-not $Proc.WaitForExit(120000)) { $Proc.Kill(); throw "Selbsttest: Zeitueberschreitung." }
if (-not (Test-Path -LiteralPath $SelfTestJson)) { throw "Selbsttest hat kein Ergebnis geschrieben (Exit $($Proc.ExitCode))." }
$Report = Get-Content -LiteralPath $SelfTestJson -Raw | ConvertFrom-Json
if ($Proc.ExitCode -ne 0 -or -not $Report.ok -or -not $Report.frozen) {
    Write-Output (Get-Content -LiteralPath $SelfTestJson -Raw)
    throw "Selbsttest der EXE fehlgeschlagen; kein Paket erzeugt."
}
Write-Output "Selbsttest der EXE: bestanden (Importtest, kein Fenster)."

# ZIP
$Zip = Join-Path $OutputDirectory "$PackageName.zip"
if (Test-Path -LiteralPath $Zip) { throw "Ausgabe existiert bereits: $Zip" }
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($AppDir, $Zip, [System.IO.Compression.CompressionLevel]::Optimal, $true)
$ZipHash = (Get-FileHash -LiteralPath $Zip -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Output "ZIP:   $Zip"
Write-Output "SHA256 $ZipHash"

# Setup (optional)
if ($Inno) {
    $SetupOut = Join-Path $BuildRoot "setup"
    New-Item -ItemType Directory -Path $SetupOut -Force | Out-Null
    Invoke-Checked $Inno @("/DAppDir=$AppDir", "/DAppVersion=$Version", "/DAppCommit=$Commit12", "/DSetupOutput=$SetupOut",
        (Join-Path $BridgeRoot "packaging/setup-app.iss"))
    $SetupName = "GSVmulti-Bruecke-Setup-$Version-$Commit12-test.exe"
    $SetupBuilt = Join-Path $SetupOut $SetupName
    if (-not (Test-Path -LiteralPath $SetupBuilt -PathType Leaf)) { throw "Setup nicht erzeugt." }
    $Setup = Join-Path $OutputDirectory $SetupName
    if (Test-Path -LiteralPath $Setup) { throw "Ausgabe existiert bereits: $Setup" }
    Move-Item -LiteralPath $SetupBuilt -Destination $Setup
    Write-Output "Setup: $Setup"
    Write-Output "SHA256 $((Get-FileHash -LiteralPath $Setup -Algorithm SHA256).Hash.ToLowerInvariant())"
}
Write-Output "Quelle: $CommitLabel  Version: $Version"
Write-Output "Unsigniert, unqualifiziert, nur interner Test. Kein Ersatz fuer build.ps1; keine Windows-Abnahme (N1/N2/N3)."
