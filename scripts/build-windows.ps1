$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not [Environment]::Is64BitProcess -or $env:OS -ne 'Windows_NT') {
    throw 'Build requires 64-bit Windows and 64-bit Python 3.11+.'
}

function Invoke-Python {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]] $Arguments)
    & python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python failed: $Arguments" }
}

Invoke-Python -m pip install '.[build]'
Invoke-Python -m unittest discover -s tests -v
# Verify the native DLL provider and bundled FFmpeg before freezing.
Invoke-Python scripts/check-runtime.py
Invoke-Python -m PyInstaller --noconfirm MiniTranscriber.spec
Invoke-Python scripts/verify-frozen.py dist/MiniTranscriber/MiniTranscriber.exe
Write-Host 'Built: dist\MiniTranscriber\MiniTranscriber.exe'
Write-Host 'Distribute the entire MiniTranscriber directory, not just its EXE.'
