param(
    [Parameter(Mandatory = $true)][string]$ArtifactPath,
    [Parameter(Mandatory = $true)][string]$CertificateBase64,
    [Parameter(Mandatory = $true)][string]$CertificatePassword,
    [Parameter(Mandatory = $true)][string]$TimestampUrl
)

$ErrorActionPreference = "Stop"
$certPath = Join-Path $env:RUNNER_TEMP "grid-resilience-codesign.pfx"
$statusPath = Join-Path (Split-Path -Parent $ArtifactPath) "GridResilienceStudio-signing-status.txt"

try {
    [IO.File]::WriteAllBytes($certPath, [Convert]::FromBase64String($CertificateBase64))
    $kitsRoot = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
    $signtool = Get-ChildItem -Path $kitsRoot -Filter "signtool.exe" -Recurse |
        Where-Object { $_.FullName -match "\\x64\\signtool\.exe$" } |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if ($null -eq $signtool) {
        throw "signtool.exe was not found in the hosted Windows SDK"
    }
    & $signtool.FullName sign /fd SHA256 /f $certPath /p $CertificatePassword /tr $TimestampUrl /td SHA256 $ArtifactPath
    if ($LASTEXITCODE -ne 0) { throw "Authenticode signing failed with exit code $LASTEXITCODE" }
    & $signtool.FullName verify /pa /all /v $ArtifactPath
    if ($LASTEXITCODE -ne 0) { throw "Authenticode verification failed with exit code $LASTEXITCODE" }
    Set-Content -Path $statusPath -Value "SIGNED: Authenticode signature verified in CI at $(Get-Date -AsUTC -Format o)" -NoNewline
}
finally {
    if (Test-Path $certPath) {
        Remove-Item -Path $certPath -Force
    }
}
