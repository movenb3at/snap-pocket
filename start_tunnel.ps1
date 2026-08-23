param(
    [string]$Cloudflared = "cloudflared",
    [ValidateRange(1, 300)]
    [int]$TimeoutSeconds = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$tunnelOrigin = "http://localhost:5000"
$tunnelUrlPath = Join-Path $PSScriptRoot "tunnel_url.txt"
$logPath = Join-Path ([System.IO.Path]::GetTempPath()) ("snap-pocket-cloudflared-{0}.log" -f $PID)
$tunnelProcess = $null
$scriptExitCode = 0

try {
    # Prevent the app from reusing an expired quick-tunnel address.
    Remove-Item -LiteralPath $tunnelUrlPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $logPath -Force -ErrorAction SilentlyContinue

    $arguments = @(
        "tunnel"
        "--url", $tunnelOrigin
        "--loglevel", "info"
        "--logfile", $logPath
    )

    $tunnelProcess = Start-Process `
        -FilePath $Cloudflared `
        -ArgumentList $arguments `
        -NoNewWindow `
        -PassThru

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $tunnelUrl = $null

    while ([DateTime]::UtcNow -lt $deadline) {
        if ($tunnelProcess.HasExited) {
            $logText = if (Test-Path -LiteralPath $logPath) {
                Get-Content -LiteralPath $logPath -Raw -ErrorAction SilentlyContinue
            } else {
                ""
            }
            throw "cloudflared exited before issuing a tunnel URL. $logText"
        }

        if (Test-Path -LiteralPath $logPath) {
            $logText = Get-Content -LiteralPath $logPath -Raw -ErrorAction SilentlyContinue
            if ($logText) {
                $match = [regex]::Match($logText, "https://[a-z0-9-]+\.trycloudflare\.com", "IgnoreCase")
                if ($match.Success) {
                    $tunnelUrl = $match.Value
                    break
                }
            }
        }

        Start-Sleep -Milliseconds 250
    }

    if (-not $tunnelUrl) {
        throw "Timed out after $TimeoutSeconds seconds while waiting for a Cloudflare quick-tunnel URL."
    }

    # app.py currently reads this file as UTF-16.
    Set-Content -LiteralPath $tunnelUrlPath -Value $tunnelUrl -Encoding Unicode -NoNewline
    Write-Host "`nCloudflare Tunnel URL saved: $tunnelUrl"
    Write-Host "Press Ctrl+C to stop the tunnel.`n"

    Wait-Process -Id $tunnelProcess.Id
    $tunnelProcess.Refresh()
    if ($tunnelProcess.ExitCode -ne 0) {
        throw "cloudflared exited with code $($tunnelProcess.ExitCode)."
    }
} catch {
    Write-Error $_
    $scriptExitCode = 1
} finally {
    if ($null -ne $tunnelProcess -and -not $tunnelProcess.HasExited) {
        Stop-Process -Id $tunnelProcess.Id -Force -ErrorAction SilentlyContinue
    }

    # A stopped tunnel must not leave an expired address behind.
    Remove-Item -LiteralPath $tunnelUrlPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $logPath -Force -ErrorAction SilentlyContinue
}

exit $scriptExitCode
