$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\James\jarvis-quant-framework\browser-mcp'
if (-not (Test-Path $repo)) {
    New-Item -ItemType Directory -Force -Path $repo | Out-Null
}
Set-Location $repo
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw 'Node.js is not available on PATH. Install Node.js first.'
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'npm is not available on PATH. Install npm first.'
}

npm init -y
npm install @modelcontextprotocol/server-puppeteer
Write-Host 'Puppeteer MCP server install script completed.'
