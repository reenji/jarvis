[CmdletBinding()]
param(
    [switch]$Voice
)

$ErrorActionPreference = "Stop"
$repositoryUrl = "git+https://github.com/reenji/jarvis.git"
$distributionName = "argus-mark-xxxix"

function Test-PythonVersion([string]$Command, [string[]]$PrefixArguments = @()) {
    try {
        $versionText = & $Command @PrefixArguments -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($LASTEXITCODE -ne 0) { return $false }
        return [version]$versionText -ge [version]"3.11"
    }
    catch {
        return $false
    }
}

$pythonSpec = $null
$launcher = Get-Command py -ErrorAction SilentlyContinue
if ($launcher) {
    foreach ($minor in @(15, 14, 13, 12, 11)) {
        $versionArgument = "-3.$minor"
        if (Test-PythonVersion -Command $launcher.Source -PrefixArguments @($versionArgument)) {
            $pythonPath = & $launcher.Source $versionArgument -c "import sys; print(sys.executable)"
            if ($LASTEXITCODE -eq 0 -and $pythonPath) {
                $pythonSpec = $pythonPath.Trim()
                break
            }
        }
    }
}

if (-not $pythonSpec) {
    foreach ($candidate in @("python3", "python")) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if (-not $command -or $command.Source -like "*\WindowsApps\*") { continue }
        if (Test-PythonVersion -Command $command.Source) {
            $pythonSpec = $command.Source
            break
        }
    }
}

if (-not $pythonSpec) {
    throw "ARGUS requires Python 3.11 or newer. Install Python, then run this script again."
}

$extras = if ($Voice) { "[voice]" } else { "" }
$packageSpec = "$distributionName$extras @ $repositoryUrl"

$uv = Get-Command uv -ErrorAction SilentlyContinue
$pipx = Get-Command pipx -ErrorAction SilentlyContinue
$argusBinDirectory = $null

if ($uv) {
    & $uv.Source tool install --python $pythonSpec $packageSpec
    if ($LASTEXITCODE -ne 0) { throw "uv could not install ARGUS." }
    $argusBinDirectory = & $uv.Source tool dir --bin
    if ($LASTEXITCODE -ne 0) { $argusBinDirectory = $null }
}
elseif ($pipx) {
    & $pipx.Source install --force --python $pythonSpec $packageSpec
    if ($LASTEXITCODE -ne 0) { throw "pipx could not install ARGUS." }
    $argusBinDirectory = & $pipx.Source environment --value PIPX_BIN_DIR
    if ($LASTEXITCODE -ne 0) { $argusBinDirectory = $null }
}
else {
    throw "Install uv or pipx first, then run this script again: https://docs.astral.sh/uv/getting-started/installation/ or https://pipx.pypa.io/stable/installation/"
}

$argusPath = $null
if ($argusBinDirectory) {
    foreach ($name in @("argus.exe", "argus")) {
        $candidatePath = Join-Path $argusBinDirectory.Trim() $name
        if (Test-Path -LiteralPath $candidatePath -PathType Leaf) {
            $argusPath = $candidatePath
            break
        }
    }
}
if (-not $argusPath) {
    $argusCommand = Get-Command argus -ErrorAction SilentlyContinue
    if ($argusCommand) { $argusPath = $argusCommand.Source }
}
if (-not $argusPath) {
    throw "ARGUS was installed, but its command was not found. Add the installer bin directory to PATH, then run 'argus setup'."
}

& $argusPath setup
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
