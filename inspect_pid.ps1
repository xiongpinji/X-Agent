param(
  [int]$TargetPid
)
$p = Get-CimInstance Win32_Process -Filter ("ProcessId=$TargetPid")
$p | Select-Object ProcessId,ParentProcessId,CommandLine | Format-List
if ($p.ParentProcessId) {
  $pp = Get-CimInstance Win32_Process -Filter ("ProcessId=$($p.ParentProcessId)")
  $pp | Select-Object ProcessId,ParentProcessId,CommandLine | Format-List
}
