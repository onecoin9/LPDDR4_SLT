param(
    [string]$Python = 'python',
    [string]$DataDir = '',
    [ValidateSet('field', 'mock')][string]$Mode = 'field',
    [string]$Output = '',
    [string]$QaKeyFile = ''
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $DataDir) { $DataDir = Join-Path $projectRoot 'local_data' }
$venvRoot = Join-Path $PSScriptRoot 'build\release_venv'
$requestedAbi = & $Python -c 'import sys,sysconfig; print(str(sys.version_info[:2])+sysconfig.get_platform())'
if ($LASTEXITCODE -ne 0) { throw 'Requested Python interpreter is unavailable' }
if (-not (Test-Path -LiteralPath (Join-Path $venvRoot 'Scripts\python.exe'))) {
    & $Python -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment initialization failed' }
}
$buildPython = Join-Path $venvRoot 'Scripts\python.exe'
$existingAbi = & $buildPython -c 'import sys,sysconfig; print(str(sys.version_info[:2])+sysconfig.get_platform())'
if ($existingAbi -ne $requestedAbi) { throw 'Existing build venv ABI differs; archive desktop\build\release_venv before rebuilding' }
$env:PYTHONUTF8 = '1'
& $buildPython -m pip install -r (Join-Path $PSScriptRoot 'requirements-build.txt')
if ($LASTEXITCODE -ne 0) { throw 'Pinned dependency installation failed' }
$buildArgs = @('-B', (Join-Path $PSScriptRoot 'build_release.py'), '--data-dir', $DataDir, '--mode', $Mode)
if ($Output) { $buildArgs += @('--output', $Output) }
if ($QaKeyFile) { $buildArgs += @('--qa-key-file', $QaKeyFile) }
& $buildPython @buildArgs
if ($LASTEXITCODE -ne 0) { throw 'Release build failed; inspect desktop\build logs' }
