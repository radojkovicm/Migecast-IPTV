<#
  End-to-end installer test (runs on a GitHub Windows runner or a clean VM).

  1. clean install (silent, per-user)            -> files + shortcuts exist
  2. bundled libVLC loads (no VLC installed)      -> --check-vlc report
  3. first start without a database               -> startup report
  4. user data seeded (favorite, progress, theme) -> upgrade over the same version
  5. data still there after upgrade               -> startup report
  6. uninstall                                    -> program gone, user data kept
  7. reinstall                                    -> data still there, starts
  Python and a system VLC are removed from PATH for every program start, so a
  hidden dependency on either would make the test fail.

  Usage: pwsh installer/test_installer.ps1 -Installer installer/Output/MigeCast-Setup-2.0.0.exe
#>
param(
  [Parameter(Mandatory = $true)][string]$Installer,
  [string]$ReportDir = "installer-test",
  # Cold start = first start after installation: Windows reads and virus-scans
  # every DLL once; the bootloader splash covers this time. Warm start = every
  # later start; this is what users experience daily.
  [int]$MaxColdWindowMs = 10000,
  [int]$MaxWarmWindowMs = 3000
)
$ErrorActionPreference = "Stop"
$Installer = (Resolve-Path $Installer).Path
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$ReportDir = (Resolve-Path $ReportDir).Path
$AppDir = Join-Path $env:LOCALAPPDATA "Programs\MigeCast"
$DataDir = Join-Path $env:LOCALAPPDATA "MigeCast"
$Exe = Join-Path $AppDir "MigeCast.exe"
$Db = Join-Path $DataDir "data\migecast.db"
$results = [ordered]@{}

function Fail($msg) { Write-Host "FAIL: $msg" -ForegroundColor Red; exit 1 }
function Ok($msg) { Write-Host "OK:   $msg" -ForegroundColor Green }

function Invoke-Setup([string[]]$SetupArgs) {
  $p = Start-Process -FilePath $Installer -ArgumentList $SetupArgs -Wait -PassThru
  if ($p.ExitCode -ne 0) { Fail "installer exit code $($p.ExitCode)" }
}

function Invoke-App([string]$Name, [string[]]$AppArgs) {
  # Clean PATH: no Python, no VLC, only Windows itself.
  $saved = $env:PATH
  $env:PATH = "$env:SystemRoot\system32;$env:SystemRoot;$env:SystemRoot\System32\Wbem"
  try {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $p = Start-Process -FilePath $Exe -ArgumentList $AppArgs -WorkingDirectory $env:TEMP -Wait -PassThru
    $sw.Stop()
  } finally { $env:PATH = $saved }
  Write-Host ("{0}: exit {1} in {2} ms" -f $Name, $p.ExitCode, $sw.ElapsedMilliseconds)
  return $p.ExitCode
}

function Read-Startup([string]$Name, [int]$LimitMs) {
  $file = Join-Path $ReportDir "$Name.json"
  if (-not (Test-Path $file)) { Fail "$($Name): startup report missing" }
  $r = Get-Content $file -Raw | ConvertFrom-Json
  $results[$Name] = $r
  $offset = [double]$r.process_to_python_ms
  $shown = [double]$r.window_shown + $offset
  # Every phase, measured from process start (bootloader included).
  $phases = ($r.PSObject.Properties | Where-Object { $_.Name -ne "process_to_python_ms" } |
    ForEach-Object { "{0}={1:N0}" -f $_.Name, ([double]$_.Value + $offset) }) -join "  "
  Write-Host ("{0}: bootloader {1:N0} ms | {2}" -f $Name, $offset, $phases)
  if ($null -eq $r.splash_closed) { Write-Host "WARNING: $($Name): bootloader splash was not active" }
  if ($shown -gt $LimitMs) { Fail "$($Name): window appeared after $([math]::Round($shown)) ms (limit $LimitMs)" }
  return $r
}

function Sql([string]$query) {
  python -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); r=c.execute(sys.argv[2]).fetchall(); c.commit(); print(r[0][0] if r and r[0] else '')" $Db $query
}

if (Test-Path "$env:ProgramFiles\VideoLAN\VLC\libvlc.dll") { Write-Host "NOTE: a system VLC exists on this machine; it is not on PATH and not used." }
if (Test-Path $DataDir) { Fail "test must start without $DataDir" }

# 1. clean install ------------------------------------------------------------
Invoke-Setup @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LOG=$ReportDir\install1.log")
if (-not (Test-Path $Exe)) { Fail "MigeCast.exe not installed" }
$desktop = [Environment]::GetFolderPath("Desktop")
$programs = [Environment]::GetFolderPath("Programs")
if (-not (Test-Path (Join-Path $desktop "MigeCast IPTV.lnk"))) { Fail "desktop shortcut missing" }
if (-not (Test-Path (Join-Path $programs "MigeCast IPTV.lnk"))) { Fail "start menu shortcut missing" }
Ok "clean install + shortcuts"

# 2. bundled VLC ----------------------------------------------------------------
$vlcReport = Join-Path $ReportDir "vlc.json"
$code = Invoke-App "check-vlc" @("--check-vlc", "`"$vlcReport`"")
$vlc = Get-Content $vlcReport -Raw | ConvertFrom-Json
if ($code -ne 0 -or -not $vlc.instance_ok) { Fail "bundled libVLC did not load" }
if ($vlc.lib_path -notlike "$AppDir*") { Fail "libVLC not loaded from the program folder: $($vlc.lib_path)" }
Ok "bundled libVLC $($vlc.libvlc_version)"

# 3. first start, no database ----------------------------------------------------
$code = Invoke-App "first-start" @("--smoke-test", "--startup-report", "`"$ReportDir\first-start.json`"")
if ($code -ne 0) { Fail "first start exit code $code" }
Read-Startup "first-start" $MaxColdWindowMs | Out-Null
if (-not (Test-Path $Db)) { Fail "database not created in $DataDir" }
if (Test-Path (Join-Path $AppDir "data")) { Fail "user data written into the program folder" }
Ok "first start creates data in %LOCALAPPDATA%\MigeCast"

# 4. seed user data, then upgrade ---------------------------------------------------
Sql "INSERT INTO favorite_vod (stream_id, name, added_at) VALUES ('ci-movie', 'CI film', datetime('now'))" | Out-Null
Sql "INSERT INTO watch_progress (stream_id, content_type, name, position_seconds, duration_seconds, last_watched, completed) VALUES ('ci-ep', 'series', 'CI epizoda', 754, 2600, datetime('now'), 0)" | Out-Null
$cfg = Join-Path $DataDir "data\config.json"
'{"appearance": {"theme": "light"}}' | Set-Content -Encoding utf8 $cfg
Invoke-Setup @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LOG=$ReportDir\upgrade.log")
$code = Invoke-App "after-upgrade" @("--smoke-test", "--startup-report", "`"$ReportDir\after-upgrade.json`"")
if ($code -ne 0) { Fail "start after upgrade exit code $code" }
Read-Startup "after-upgrade" $MaxColdWindowMs | Out-Null
if ((Sql "SELECT count(*) FROM favorite_vod WHERE stream_id='ci-movie'") -ne "1") { Fail "favorite lost on upgrade" }
if ((Sql "SELECT position_seconds FROM watch_progress WHERE stream_id='ci-ep'") -ne "754") { Fail "watch progress lost on upgrade" }
if ((Get-Content $cfg -Raw) -notmatch '"light"') { Fail "settings lost on upgrade" }
Ok "upgrade keeps favorites, progress and settings"

# 5. uninstall ------------------------------------------------------------------------
$uninstaller = Get-ChildItem $AppDir -Filter "unins*.exe" | Select-Object -First 1
$p = Start-Process -FilePath $uninstaller.FullName -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") -Wait -PassThru
Start-Sleep -Seconds 3
if (Test-Path $Exe) { Fail "program still installed after uninstall" }
if (-not (Test-Path $Db)) { Fail "uninstall removed the user database" }
if (Test-Path (Join-Path $desktop "MigeCast IPTV.lnk")) { Fail "desktop shortcut left after uninstall" }
Ok "uninstall removes program, keeps user data"

# 6. reinstall -------------------------------------------------------------------------
Invoke-Setup @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LOG=$ReportDir\install2.log")
$code = Invoke-App "after-reinstall" @("--smoke-test", "--startup-report", "`"$ReportDir\after-reinstall.json`"")
if ($code -ne 0) { Fail "start after reinstall exit code $code" }
Read-Startup "after-reinstall" $MaxColdWindowMs | Out-Null
if ((Sql "SELECT count(*) FROM favorite_vod WHERE stream_id='ci-movie'") -ne "1") { Fail "favorite lost after reinstall" }
Ok "reinstall restores user data"

# 7. warm start timing (5 runs) -------------------------------------------------------------
$times = @()
foreach ($i in 1..5) {
  Invoke-App "warm-$i" @("--smoke-test", "--startup-report", "`"$ReportDir\warm-$i.json`"") | Out-Null
  $r = Read-Startup "warm-$i" $MaxColdWindowMs
  $times += [double]$r.window_shown + [double]$r.process_to_python_ms
}
$avg = ($times | Measure-Object -Average).Average
Write-Host ("Warm start: window shown after {0:N0} ms on average (min {1:N0}, max {2:N0})" -f $avg, ($times | Measure-Object -Minimum).Minimum, ($times | Measure-Object -Maximum).Maximum)
if ($avg -gt $MaxWarmWindowMs) { Fail ("warm start too slow: {0:N0} ms average (limit {1} ms)" -f $avg, $MaxWarmWindowMs) }
$results | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $ReportDir "summary.json")
Ok "all installer tests passed"
