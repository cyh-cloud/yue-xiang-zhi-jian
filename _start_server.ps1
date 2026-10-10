# 以 run.py 相同的参数拉起 Flask（host=0.0.0.0，debug=False, use_reloader=False；
# 端口取 .env 的 PORT，留空/非法回落默认 5000，多工作树可各自改端口避免冲突），
# 区别有两点：
#   1. 不自动打开系统浏览器（手动测试时不想抢焦点，内嵌浏览器已经开着）；
#   2. 清掉 HTTP_PROXY/HTTPS_PROXY/ALL_PROXY —— 本机沙箱会把这些指向 127.0.0.1:9
#      死端口，不清则所有 AI 接口调用报 ProxyError。
# PID 写入 data\server.pid，日志覆盖写 data\server.log / data\server.err.log。
# 用法：powershell -File _start_server.ps1
$root = $PSScriptRoot
$env:HTTP_PROXY = ''
$env:HTTPS_PROXY = ''
$env:ALL_PROXY = ''

$py = Join-Path $root '.venv\Scripts\python.exe'
$serve = Join-Path $root '_serve.py'

# 端口与 run.py / _serve.py 同一解析逻辑，健康检查跟着实际端口走。
# Select-Object -Last 1 防止 resolve_port 的警告行混进结果。
Push-Location $root
try {
    $port = & $py -c "from run import resolve_port; print(resolve_port()[0])" | Select-Object -Last 1
} finally {
    Pop-Location
}
if (-not $port) { $port = 5000 }

$p = Start-Process -FilePath $py -ArgumentList $serve `
    -WorkingDirectory $root -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $root 'data\server.log') `
    -RedirectStandardError (Join-Path $root 'data\server.err.log') `
    -PassThru

$p.Id | Set-Content -LiteralPath (Join-Path $root 'data\server.pid')
"pid=$($p.Id)"
Start-Sleep -Seconds 3
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/index.html" -UseBasicParsing -TimeoutSec 8
    "health=$($r.StatusCode)"
} catch {
    "health FAILED: $($_.Exception.Message)"
}
