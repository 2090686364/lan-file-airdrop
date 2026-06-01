@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   一键打包成exe文件
echo ========================================
echo.

REM 检查Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误：未检测到Python
    pause
    exit /b 1
)

echo ✅ Python环境正常
echo.
echo 📦 开始打包...
echo.

python 打包exe.py

echo.
pause

