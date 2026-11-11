# Configure pip to use Tsinghua mirror (user-level, persistent)
$pipDir = Join-Path $env:APPDATA "pip"
$pipIni = Join-Path $pipDir "pip.ini"
New-Item -ItemType Directory -Force -Path $pipDir | Out-Null

$content = @"
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
trusted-host = pypi.tuna.tsinghua.edu.cn
timeout = 120
"@

[System.IO.File]::WriteAllText($pipIni, $content, [System.Text.UTF8Encoding]::new($false))
Write-Host "pip mirror -> Tsinghua ($pipIni)" -ForegroundColor Green
python -m pip config list
