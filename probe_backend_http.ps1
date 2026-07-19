$ErrorActionPreference = 'Stop'
$urls = @(
  'http://127.0.0.1:8003/',
  'http://127.0.0.1:8003/docs',
  'http://127.0.0.1:8003/openapi.json'
)
foreach ($u in $urls) {
  try {
    $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 5
    Write-Output ("URL=$u STATUS=$($r.StatusCode) LEN=$($r.Content.Length)")
  }
  catch {
    Write-Output ("URL=$u ERROR=$($_.Exception.Message)")
  }
}
