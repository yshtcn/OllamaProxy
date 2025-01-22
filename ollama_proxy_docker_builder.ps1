# Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

# 检查是否以管理员权限运行
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    # 请求管理员权限
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

# 检查 Docker 是否已安装并可用
$dockerPath = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerPath) {
    Write-Host "未找到 Docker 命令。请检查：" -ForegroundColor Red
    Write-Host "1. Docker Desktop 是否已安装" -ForegroundColor Yellow
    Write-Host "2. Docker Desktop 是否正在运行" -ForegroundColor Yellow
    Write-Host "3. 环境变量是否正确设置" -ForegroundColor Yellow
    Write-Host "`n典型的 Docker 安装路径为：C:\Program Files\Docker\Docker\resources\bin" -ForegroundColor Yellow
    Write-Host "您可能需要将此路径添加到系统的 PATH 环境变量中" -ForegroundColor Yellow
    
    $response = Read-Host "是否要打开系统环境变量设置？(Y/N)"
    if ($response -eq 'Y' -or $response -eq 'y') {
        Start-Process "SystemPropertiesAdvanced.exe"
    }
    exit
}

# 检查 Docker 服务是否运行
try {
    $dockerVersion = docker version
    if ($LASTEXITCODE -ne 0) {
        throw "Docker 服务未运行"
    }
} catch {
    Write-Host "Docker 服务似乎没有正常运行。请检查：" -ForegroundColor Red
    Write-Host "1. Docker Desktop 是否已启动" -ForegroundColor Yellow
    Write-Host "2. 等待 Docker Desktop 完全启动" -ForegroundColor Yellow
    exit
}

# 切换到脚本所在目录
Set-Location $PSScriptRoot
Write-Host "当前目录已切换为脚本所在目录: $PSScriptRoot"

# 获取当前日期和时间
$dateTime = Get-Date -Format "yyyyMMdd"
Write-Host "当前日期: $dateTime"

# 提示输入并获取版本号最后一位
$revision = Read-Host -Prompt "请输入版本号 ($dateTime,如果没有次数，请直接回车)"
Write-Host "输入的版本号: $revision"

# 构造版本号
if ([string]::IsNullOrWhiteSpace($revision)) {
    $version = "$dateTime"
} else {
    $version = "$dateTime" + "_$revision"
}
Write-Host "完整的版本号: $version"

# 构建带完整版本号标签的 Docker 镜像
Write-Host "正在构建 Docker 镜像..."
$tempFileBuild = [System.IO.Path]::GetTempFileName()
docker build -t yshtcn/ollama-proxy:$version . 2> $tempFileBuild

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker 镜像构建失败" -ForegroundColor Red
    Write-Host (Get-Content $tempFileBuild) -ForegroundColor Red
    Remove-Item $tempFileBuild
    exit
}
Write-Host "Docker 镜像构建成功"
Remove-Item $tempFileBuild

# 推送带完整版本号标签的 Docker 镜像到 Docker Hub
Write-Host "正在推送 Docker 镜像到 Docker Hub..."
$tempFilePush = [System.IO.Path]::GetTempFileName()
docker push yshtcn/ollama-proxy:$version 2> $tempFilePush

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker 镜像推送失败" -ForegroundColor Red
    Write-Host (Get-Content $tempFilePush) -ForegroundColor Red
    Remove-Item $tempFilePush
    exit
}
Write-Host "Docker 镜像推送成功"
Remove-Item $tempFilePush

# 为镜像打上 'latest' 标签并推送
Write-Host "正在为镜像打上 'latest' 标签并推送..."
$tempFilePushLatest = [System.IO.Path]::GetTempFileName()
docker tag yshtcn/ollama-proxy:$version yshtcn/ollama-proxy:latest
docker push yshtcn/ollama-proxy:latest 2> $tempFilePushLatest

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker 镜像 'latest' 标签推送失败" -ForegroundColor Red
    Write-Host (Get-Content $tempFilePushLatest) -ForegroundColor Red
    Remove-Item $tempFilePushLatest
    exit
}
Write-Host "Docker 镜像 'latest' 标签推送成功"
Remove-Item $tempFilePushLatest

Write-Host "Docker 镜像构建和推送全部完成" 

# 等待用户确认后再关闭
Write-Host "`n按回车键退出..." -ForegroundColor Green
$null = Read-Host 