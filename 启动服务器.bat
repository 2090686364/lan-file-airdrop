@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   局域网文件空投系统 - 启动脚本
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误：未检测到Python，请先安装Python 3.8+
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ 已检测到Python
echo.

REM 检查是否已安装依赖
python -c "import fastapi" >nul 2>&1
if %errorlevel% neq 0 (
    echo 📦 首次运行，正在安装依赖...
    echo.
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo ❌ 依赖安装失败，请检查网络连接或尝试手动安装：
        echo    python -m pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo.
    echo ✅ 依赖安装完成
    echo.
)

echo 🚀 正在启动服务器...
echo.
python server.py

pause

