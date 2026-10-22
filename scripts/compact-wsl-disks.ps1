# Run in an ADMINISTRATOR PowerShell, after quitting Docker Desktop from the tray.
# Shrinks the Docker and Ubuntu WSL disk files. Deletes nothing inside them.
$ErrorActionPreference = 'Stop'

$disks = @(
    "$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx",
    "$env:LOCALAPPDATA\Packages\CanonicalGroupLimited.Ubuntu_79rhkp1fndgsc\LocalState\ext4.vhdx"
)

if (Get-Process 'Docker Desktop', 'com.docker.backend' -ErrorAction SilentlyContinue) {
    throw 'Docker Desktop is still running. Quit it from the tray icon first.'
}
wsl --shutdown
Start-Sleep 8

foreach ($d in $disks) {
    if (-not (Test-Path $d)) { Write-Host "SKIP (not found): $d"; continue }
    $before = [math]::Round((Get-Item $d).Length / 1GB, 1)
    Write-Host "Compacting $d ($before GB) ..."
    $script = Join-Path $env:TEMP 'compact.diskpart'
    @("select vdisk file=`"$d`"", 'attach vdisk readonly', 'compact vdisk', 'detach vdisk', 'exit') |
        Set-Content $script -Encoding ascii
    diskpart /s $script
    $after = [math]::Round((Get-Item $d).Length / 1GB, 1)
    Write-Host "  $before GB -> $after GB"
}
Get-PSDrive C | ForEach-Object { Write-Host ("C: free {0} GB" -f [math]::Round($_.Free / 1GB, 1)) }
