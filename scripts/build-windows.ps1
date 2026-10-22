$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not [Environment]::Is64BitProcess -or $env:OS -ne 'Windows_NT') {
    throw 'Build requires 64-bit Windows and 64-bit Python 3.11+.'
}

function Invoke-Python {
    param([string[]] $PythonArgs)
    & python @PythonArgs
    if ($LASTEXITCODE -ne 0) { throw "Python failed: $PythonArgs" }
}

Invoke-Python -PythonArgs @('-m', 'pip', 'install', '-e', '.[build]')
Invoke-Python -PythonArgs @('-m', 'unittest', 'discover', '-s', 'tests', '-v')
# Verify the native DLL provider and bundled FFmpeg before freezing.
Invoke-Python -PythonArgs @('scripts/check-runtime.py')
Invoke-Python -PythonArgs @('-m', 'PyInstaller', '--noconfirm', 'MiniTranscriber.spec')
Invoke-Python -PythonArgs @('scripts/verify-frozen.py', 'dist/MiniTranscriber/MiniTranscriber.exe')
Write-Host 'Built: dist\MiniTranscriber\MiniTranscriber.exe'
Write-Host 'Distribute the entire MiniTranscriber directory, not just its EXE.'
