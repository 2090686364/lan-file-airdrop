#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键打包脚本 - 将系统打包成单个exe文件
"""

import os
import sys
import subprocess
from pathlib import Path


def check_pyinstaller():
    """检查PyInstaller是否安装"""
    try:
        import PyInstaller
        return True
    except ImportError:
        return False


def install_pyinstaller():
    """安装PyInstaller"""
    print("📦 正在安装 PyInstaller...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller 安装成功")
        return True
    except:
        print("❌ PyInstaller 安装失败")
        return False


def create_spec_file():
    """创建PyInstaller配置文件"""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['server.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('index.html', '.'),
    ],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL.ImageQt',
        'PyQt5',
        'tkinter',
        'cryptography',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='文件空投系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # 启用UPX压缩
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
'''
    
    with open("打包配置.spec", "w", encoding="utf-8") as f:
        f.write(spec_content)
    
    print("✅ 已创建打包配置文件: 打包配置.spec")


def build_exe():
    """执行打包"""
    print("\n" + "=" * 60)
    print("📦 开始打包...")
    print("=" * 60)
    print()
    
    # 创建spec文件
    create_spec_file()
    
    print("⏳ 正在打包，请稍候（可能需要几分钟）...")
    print()
    
    # 执行PyInstaller
    try:
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "打包配置.spec", "--clean"],
            capture_output=False,
            text=True
        )
        
        if result.returncode == 0:
            print()
            print("=" * 60)
            print("✅ 打包成功！")
            print("=" * 60)
            print()
            
            exe_path = Path("dist/文件空投系统.exe")
            if exe_path.exists():
                size_mb = exe_path.stat().st_size / 1024 / 1024
                print(f"📦 文件位置: {exe_path.absolute()}")
                print(f"📊 文件大小: {size_mb:.2f} MB")
                print()
                print("🚀 使用方法:")
                print(f"   直接运行: {exe_path}")
                print("   或双击打开")
                print()
                print("💡 提示:")
                print("   - exe文件可以复制到其他电脑直接使用")
                print("   - 无需安装Python环境")
                print("   - 首次运行可能被杀毒软件拦截（添加信任即可）")
                print()
            else:
                print("⚠️  打包完成但找不到exe文件")
                print("   请检查 dist 目录")
            
            return True
        else:
            print("❌ 打包失败")
            return False
            
    except Exception as e:
        print(f"❌ 打包过程出错: {e}")
        return False


def main():
    print()
    print("=" * 60)
    print("🎯 局域网文件空投系统 - 一键打包工具")
    print("=" * 60)
    print()
    print("功能: 将系统打包成单个exe文件")
    print("优点: ")
    print("  ✅ 无需Python环境")
    print("  ✅ 一个文件包含所有功能")
    print("  ✅ 自动UPX压缩，体积更小")
    print("  ✅ 可在任何Windows电脑运行")
    print()
    
    # 检查必要文件
    if not Path("server.py").exists():
        print("❌ 错误：找不到 server.py")
        print("   请在项目目录中运行此脚本")
        return
    
    if not Path("index.html").exists():
        print("❌ 错误：找不到 index.html")
        return
    
    # 检查PyInstaller
    if not check_pyinstaller():
        print("📦 检测到未安装 PyInstaller")
        response = input("是否现在安装？[Y/n]: ")
        if response.lower() != 'n':
            if not install_pyinstaller():
                return
        else:
            print("❌ 已取消")
            return
    
    print("✅ PyInstaller 已就绪")
    print()
    
    # 确认打包
    response = input("📦 开始打包？[Y/n]: ")
    if response.lower() == 'n':
        print("❌ 已取消")
        return
    
    # 执行打包
    if build_exe():
        print("=" * 60)
        print("🎉 打包完成！")
        print("=" * 60)
    else:
        print("=" * 60)
        print("❌ 打包失败")
        print("=" * 60)
        print()
        print("常见问题：")
        print("1. 确保已安装所有依赖: pip install -r requirements.txt")
        print("2. 磁盘空间是否充足（需要约500MB）")
        print("3. 杀毒软件是否阻止PyInstaller")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ 用户取消")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
    finally:
        input("\n按回车键退出...")

