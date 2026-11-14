# Requires Windows PowerShell 5.1+ or PowerShell 7, explicit Windows Python >=3.13 x64.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BuildPython,
    [Parameter(Mandatory = $true)][string]$VerifiedInputs,
    [string]$OutputDirectory = (Join-Path $PSScriptRoot "dist"),
    [switch]$SelfTest,
    [switch]$BuildInternalProbeSetup,
    [string]$InnoCompiler
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
if ($BuildInternalProbeSetup) {
    if (-not $InnoCompiler) { throw "Internal probe setup requires an explicitly selected, locally qualified Inno Setup compiler; no PATH discovery." }
    $InnoCompiler = (Resolve-Path -LiteralPath $InnoCompiler).Path
}
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

# Optional packaging of the SAME qualified runtime probe. No product GUI/helper
# or driver is added. The existing Windows/locks/evidence/self-test gates above
# remain mandatory. No product release signature or Windows acceptance is claimed.
if ($BuildInternalProbeSetup) {
    $VerifyProbeCode = "import json,runpy,sys; from pathlib import Path; support=runpy.run_path(sys.argv[1]); package=Path(sys.argv[2]); manifest=json.loads((package/'build-manifest.json').read_text(encoding='utf-8')); support['verify_tree'](package, manifest['files'])"
    Invoke-Checked $Python @("-I", "-c", $VerifyProbeCode, $Support, $Destination)
    $ProbeSetupRecipe = Join-Path $BridgeRoot "packaging/setup.iss"
    $ProbeRecipeHash = (Get-FileHash -LiteralPath $ProbeSetupRecipe -Algorithm SHA256).Hash.ToLowerInvariant()
    $ProbeManifestHash = (Get-FileHash -LiteralPath (Join-Path $Destination "build-manifest.json") -Algorithm SHA256).Hash.ToLowerInvariant()
    $InnoCompilerHash = (Get-FileHash -LiteralPath $InnoCompiler -Algorithm SHA256).Hash.ToLowerInvariant()
    $InternalSetupOutput = Join-Path $BuildRoot "internal-probe-setup"
    New-Item -ItemType Directory -Path $InternalSetupOutput -Force | Out-Null
    Invoke-Checked $InnoCompiler @("/DProbePackage=$Destination", "/DProbeCommit=$($Commit.Substring(0,12))", "/DProbeBuildId=$BuildId", "/DProbeOutput=$InternalSetupOutput", $ProbeSetupRecipe)
    Invoke-Checked $Python @("-I", "-c", $VerifyProbeCode, $Support, $Destination)
    $InternalSetupName = "internal-probe-setup-$($Commit.Substring(0,12))-$BuildId.exe"
    $InternalSetup = Join-Path $InternalSetupOutput $InternalSetupName
    if (-not (Test-Path -LiteralPath $InternalSetup -PathType Leaf)) { throw "Internal probe setup output missing." }
    $InternalSetupHash = (Get-FileHash -LiteralPath $InternalSetup -Algorithm SHA256).Hash.ToLowerInvariant()
    if ((Get-FileHash -LiteralPath $ProbeSetupRecipe -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ProbeRecipeHash) { throw "Internal probe setup recipe changed during compile." }
    if ((Get-FileHash -LiteralPath $InnoCompiler -Algorithm SHA256).Hash.ToLowerInvariant() -ne $InnoCompilerHash) { throw "Inno compiler changed during compile." }
    if ((Get-FileHash -LiteralPath (Join-Path $Destination "build-manifest.json") -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ProbeManifestHash) { throw "N1 manifest changed during setup compile." }
    # Keep original compiler/version/hash and input manifest hash beside this
    # internal artifact; this unsigned record is not an authenticated release.
    $InternalRecord = [ordered]@{
        schema_version = 1
        status = "internal_unsigned_probe_setup_unqualified"
        release_signed = $false
        source_commit = $Commit
        setup = $InternalSetupName
        setup_sha256 = $InternalSetupHash
        n1_manifest_sha256 = $ProbeManifestHash
        setup_recipe_sha256 = $ProbeRecipeHash
        inno_compiler_sha256 = $InnoCompilerHash
        inno_compiler_version = (Get-Item -LiteralPath $InnoCompiler).VersionInfo.FileVersion
    }
    $InternalRecord | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $InternalSetupOutput "internal-setup-build.json") -Encoding UTF8
    Write-Output "Internal unsigned probe setup (not Windows-qualified): $InternalSetup"
}
