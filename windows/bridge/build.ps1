# Requires Windows PowerShell 5.1+ or PowerShell 7, explicit Windows Python >=3.13 x64.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BuildPython,
    [Parameter(Mandatory = $true)][string]$VerifiedInputs,
    [string]$OutputDirectory = (Join-Path $PSScriptRoot "dist"),
    [switch]$SelfTest
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    # pip --isolated alone still reads machine-wide configuration. Disable it
    # in children as well, so an extra-index/trusted-host cannot change policy.
    $PreviousPipConfig = [Environment]::GetEnvironmentVariable("PIP_CONFIG_FILE", "Process")
    try {
        $env:PIP_CONFIG_FILE = "NUL"
        & $Program @Arguments
        if ($LASTEXITCODE -ne 0) { throw "Command failed (exit $LASTEXITCODE): $Program" }
    }
    finally {
        if ($null -eq $PreviousPipConfig) {
            Remove-Item Env:PIP_CONFIG_FILE -ErrorAction SilentlyContinue
        }
        else { $env:PIP_CONFIG_FILE = $PreviousPipConfig }
    }
}

if ($env:OS -ne "Windows_NT") { throw "Build blocked: use a Windows 11 x64 build host." }
$BuildPython = (Resolve-Path -LiteralPath $BuildPython).Path
$VerifiedInputs = (Resolve-Path -LiteralPath $VerifiedInputs).Path
$BridgeRoot = $PSScriptRoot
$RepoRoot = (Resolve-Path (Join-Path $BridgeRoot "../..")).Path
$Support = Join-Path $BridgeRoot "packaging/build_support.py"
# Python-3.7-compatible precheck: never discover/change a system interpreter via PATH/py.exe.
Invoke-Checked $BuildPython @("-I", "-c", "import sys; sys.exit(0 if sys.version_info >= (3,13) else 'Build blocked: select Python >=3.13 explicitly; existing Python remains unchanged.')")
Invoke-Checked $BuildPython @("-I", $Support, "preflight", "--bridge-root", $BridgeRoot, "--verification", $VerifiedInputs)

$Commit = (& git -C $RepoRoot rev-parse HEAD)
if ($LASTEXITCODE -ne 0) { throw "Source Git commit unavailable." }
$Commit = $Commit.Trim()
$BuildId = [Guid]::NewGuid().ToString("N")
$BuildRoot = Join-Path $BridgeRoot ".build/$BuildId"
$Venv = Join-Path $BuildRoot ".build-venv"
$Python = Join-Path $Venv "Scripts/python.exe"
$Wheelhouse = Join-Path $BuildRoot "wheelhouse"
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
$StageParent = Join-Path $OutputDirectory ".partial-$BuildId"
$Stage = Join-Path $StageParent "dispread-bridge-probe"
$Destination = Join-Path $OutputDirectory "dispread-bridge-$($Commit.Substring(0,12))-$BuildId"
$BuildLock = Join-Path $BridgeRoot "requirements-build.lock"
$Snapshot = Join-Path $BuildRoot "source-snapshot.json"

# Fresh isolated Windows environment; the Pi .venv is never used or changed.
New-Item -ItemType Directory -Path $BuildRoot, $Wheelhouse, $OutputDirectory, $StageParent -Force | Out-Null
Invoke-Checked $BuildPython @("-I", $Support, "snapshot", "--bridge-root", $BridgeRoot, "--verification", $VerifiedInputs, "--source-root", $RepoRoot, "--source-commit", $Commit, "--snapshot", $Snapshot)
Invoke-Checked $BuildPython @("-I", "-m", "venv", $Venv)
Invoke-Checked $Python @("-I", "-m", "pip", "--isolated", "download", "--index-url", "https://pypi.org/simple", "--require-hashes", "--only-binary=:all:", "--dest", $Wheelhouse, "-r", $BuildLock)
Invoke-Checked $Python @("-I", "-m", "pip", "--isolated", "install", "--no-index", "--find-links", $Wheelhouse, "--require-hashes", "--only-binary=:all:", "--no-deps", "-r", $BuildLock)
Invoke-Checked $Python @("-I", "-m", "pip", "check")
Invoke-Checked $Python @("-I", $Support, "installed", "--bridge-root", $BridgeRoot, "--verification", $VerifiedInputs)
Invoke-Checked $Python @("-I", "-m", "PyInstaller", "--clean", "--noconfirm", "--distpath", $StageParent, "--workpath", (Join-Path $BuildRoot "pyinstaller"), (Join-Path $BridgeRoot "packaging/bridge.spec"))

# Self-test is mandatory even without -SelfTest. Partial outputs are never releases.
# Move only within the output filesystem; no prior package is replaced.
$SiblingStage = Join-Path $OutputDirectory ".verified-stage-$BuildId"
Move-Item -LiteralPath $Stage -Destination $SiblingStage
Invoke-Checked $Python @("-I", $Support, "finalize", "--bridge-root", $BridgeRoot, "--verification", $VerifiedInputs, "--stage", $SiblingStage, "--destination", $Destination, "--source-root", $RepoRoot, "--source-commit", $Commit, "--snapshot", $Snapshot)
Write-Output "Internal unsigned probe package: $Destination"
Write-Output "N1 acceptance still requires clean VM tests without Python and alongside unchanged Python 3.7."
