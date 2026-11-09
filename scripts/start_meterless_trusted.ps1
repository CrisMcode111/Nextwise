# Start the installed daemon with Node's supported Windows system CA trust.
# Only the daemon and its children inherit this setting; no vendor files change.
# Use -Restart for an existing idle daemon; omit it when the daemon is stopped.
# Future starts must use this launcher to retain the process-scoped trust option.
param([switch]$Restart)

$ErrorActionPreference = 'Stop'
$installation = Join-Path $env:LOCALAPPDATA 'Nightshift'
$daemon = Join-Path $installation 'meterlessd.exe'
$node = Join-Path $installation 'node\node.exe'
$cli = Join-Path $installation 'cli\ns.cmd'
if (-not (Test-Path -LiteralPath $daemon -PathType Leaf) -or
    -not (Test-Path -LiteralPath $node -PathType Leaf)) {
    throw 'The existing Nightshift installation was not found.'
}
if ($env:NODE_TLS_REJECT_UNAUTHORIZED -eq '0') {
    throw 'Refusing to start while inherited TLS certificate verification is disabled.'
}

$runningDaemons = @(Get-Process -Name 'meterlessd' -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $daemon })
if (-not $Restart -and $runningDaemons.Count -gt 0) {
    throw 'Meterless is already running. Use -Restart to apply trust after confirming its queue is idle.'
}

if ($Restart) {
    # A restart must not interrupt a running or queued model job.
    $statusText = & $cli status --json 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'Could not confirm that the existing daemon is idle.' }
    $status = $statusText | ConvertFrom-Json
    if (-not $status.ok -or $null -eq $status.data.jobs -or
        $null -eq $status.data.jobs.running -or $null -eq $status.data.jobs.queued -or
        $status.data.jobs.running -ne 0 -or $status.data.jobs.queued -ne 0) {
        throw 'The daemon must have no running or queued jobs before a trust-setting restart.'
    }
}

$previousOptions = [Environment]::GetEnvironmentVariable('NODE_OPTIONS', 'Process')
try {
    $env:NODE_OPTIONS = (($previousOptions + ' --use-system-ca').Trim())
    if ($Restart) {
        $previousDaemons = $runningDaemons
        # Windows PowerShell 5 treats the daemon's informational stderr as an
        # error record. Capture it and decide from the native exit code instead.
        $previousErrorAction = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $stopOutput = & $daemon --stop 2>&1
            $stopExitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $previousErrorAction
        }
        if ($stopExitCode -ne 0) { throw 'The existing daemon could not be stopped; output withheld.' }
        foreach ($previousDaemon in $previousDaemons) {
            if (-not $previousDaemon.WaitForExit(10000)) {
                throw 'The existing daemon has not finished stopping; no second instance was launched.'
            }
        }
    }
    $started = Start-Process -FilePath $daemon -WorkingDirectory $installation -WindowStyle Hidden -PassThru
    Write-Output ('Started Meterless with system CA trust; certificate verification remains enabled. PID: ' + $started.Id)
} finally {
    [Environment]::SetEnvironmentVariable('NODE_OPTIONS', $previousOptions, 'Process')
}
