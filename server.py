#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
局域网文件空投系统 - 服务器端
阶段二：断点续传 + 反向空投
"""

import os
import sys
import socket
import qrcode
import webbrowser
import threading
import time
import hashlib
import json
import uuid
import pyperclip
import asyncio
from pathlib import Path
from typing import List, Optional, Dict
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Header, Request
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime
import socketio


# 获取资源文件路径（兼容PyInstaller打包）
def get_resource_path(relative_path):
    """获取资源文件的绝对路径（兼容打包后的exe）"""
    try:
        # PyInstaller创建临时文件夹，路径存储在_MEIPASS中
        base_path = sys._MEIPASS
    except Exception:
        # 未打包时使用当前目录
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

# 创建Socket.IO服务器
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=False,
    engineio_logger=False
)

# 创建应用
app = FastAPI(title="局域网文件空投系统")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载Socket.IO
socket_app = socketio.ASGIApp(sio, app)

# 获取exe运行目录（打包后使用）
def get_exe_dir():
    """获取exe文件所在目录"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的exe
        return os.path.dirname(sys.executable)
    else:
        # 如果是Python脚本
        return os.path.dirname(os.path.abspath(__file__))

# 配置上传目录（在exe所在目录创建）
exe_dir = Path(get_exe_dir())
UPLOAD_DIR = exe_dir / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# 配置分块上传临时目录
CHUNKS_DIR = exe_dir / "chunks"
CHUNKS_DIR.mkdir(exist_ok=True)

# 配置反向空投目录（电脑推送到手机的文件）
SEND_DIR = exe_dir / "send_files"
SEND_DIR.mkdir(exist_ok=True)

# 全局变量：存储待下载的文件队列
pending_downloads: Dict[str, dict] = {}

# 全局变量：剪贴板历史
clipboard_history: List[dict] = []
last_clipboard_content = ""


def get_local_ip():
    """获取本机局域网IP地址"""
    try:
        # 创建一个UDP socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 连接到外部地址（不需要真的连接）
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


def generate_qrcode(url: str):
    """生成二维码并在终端显示"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    # 在终端打印二维码
    qr.print_ascii(invert=True)


@app.get("/", response_class=HTMLResponse)
async def get_upload_page():
    """返回上传页面"""
    html_path = get_resource_path("index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


@app.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    paths: List[str] = Form(None)
):
    """
    处理文件上传
    支持多文件和文件夹上传
    """
    try:
        uploaded_files = []
        
        for idx, file in enumerate(files):
            # 获取相对路径（用于文件夹上传）
            if paths and idx < len(paths):
                relative_path = paths[idx]
            else:
                relative_path = file.filename
            
            # 构建完整保存路径
            file_path = UPLOAD_DIR / relative_path
            
            # 创建必要的目录
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存文件
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            
            uploaded_files.append({
                "filename": file.filename,
                "path": relative_path,
                "size": len(content)
            })
            
            print(f"✅ 已保存: {relative_path} ({len(content) / 1024 / 1024:.2f} MB)")
        
        return {
            "status": "success",
            "message": f"成功上传 {len(uploaded_files)} 个文件",
            "files": uploaded_files
        }
    
    except Exception as e:
        print(f"❌ 上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload_chunk")
async def upload_chunk(
    file_id: str = Form(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    filename: str = Form(...),
    relative_path: str = Form(None),
    is_shared: str = Form("true"),
    chunk: UploadFile = File(...)
):
    """
    分块上传接口（支持断点续传）
    默认上传到共享区
    """
    try:
        # 创建文件专用的临时目录
        file_chunk_dir = CHUNKS_DIR / file_id
        file_chunk_dir.mkdir(exist_ok=True)
        
        # 保存当前分块
        chunk_path = file_chunk_dir / f"chunk_{chunk_index}"
        content = await chunk.read()
        with open(chunk_path, "wb") as f:
            f.write(content)
        
        # 检查是否所有分块都已上传
        uploaded_chunks = list(file_chunk_dir.glob("chunk_*"))
        
        # 如果所有分块都上传完成，合并文件
        if len(uploaded_chunks) == total_chunks:
            # 所有文件都保存到共享区
            save_path = relative_path if relative_path else filename
            final_path = SEND_DIR / save_path
            final_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 合并所有分块
            with open(final_path, "wb") as final_file:
                for i in range(total_chunks):
                    chunk_file = file_chunk_dir / f"chunk_{i}"
                    with open(chunk_file, "rb") as cf:
                        final_file.write(cf.read())
            
            # 删除临时分块
            for chunk_file in uploaded_chunks:
                chunk_file.unlink()
            file_chunk_dir.rmdir()
            
            # 添加到共享文件列表
            download_id = str(uuid.uuid4())
            pending_downloads[download_id] = {
                "id": download_id,
                "filename": final_path.name,
                "path": str(final_path),
                "size": final_path.stat().st_size,
                "timestamp": datetime.now().isoformat()
            }
            
            print(f"✅ 已完成并添加到共享区: {save_path} (合并{total_chunks}个分块)")
            
            return {
                "status": "completed",
                "message": "文件上传完成",
                "filename": filename,
                "total_chunks": total_chunks
            }
        else:
            return {
                "status": "uploading",
                "message": f"分块 {chunk_index + 1}/{total_chunks} 上传成功",
                "uploaded_chunks": len(uploaded_chunks),
                "total_chunks": total_chunks
            }
    
    except Exception as e:
        print(f"❌ 分块上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/check_chunks/{file_id}")
async def check_chunks(file_id: str):
    """
    检查已上传的分块（用于断点续传）
    """
    file_chunk_dir = CHUNKS_DIR / file_id
    if not file_chunk_dir.exists():
        return {"uploaded_chunks": []}
    
    uploaded_chunks = []
    for chunk_file in file_chunk_dir.glob("chunk_*"):
        chunk_index = int(chunk_file.name.split("_")[1])
        uploaded_chunks.append(chunk_index)
    
    return {"uploaded_chunks": sorted(uploaded_chunks)}


@app.post("/share_files")
async def share_files(files: List[UploadFile] = File(...)):
    """
    上传文件到共享区（供其他设备下载）
    """
    try:
        shared_files = []
        import shutil
        
        for file in files:
            # 生成唯一下载ID
            download_id = str(uuid.uuid4())
            
            # 保存文件到共享目录
            dest_path = SEND_DIR / file.filename
            counter = 1
            while dest_path.exists():
                stem = Path(file.filename).stem
                suffix = Path(file.filename).suffix
                dest_path = SEND_DIR / f"{stem}_{counter}{suffix}"
                counter += 1
            
            # 保存文件
            with open(dest_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # 添加到待下载队列
            pending_downloads[download_id] = {
                "id": download_id,
                "filename": dest_path.name,
                "path": str(dest_path),
                "size": dest_path.stat().st_size,
                "timestamp": datetime.now().isoformat()
            }
            
            shared_files.append(dest_path.name)
            print(f"📤 已添加到共享区: {dest_path.name}")
        
        return {
            "status": "success",
            "message": f"成功添加 {len(shared_files)} 个文件",
            "files": shared_files
        }
    
    except Exception as e:
        print(f"❌ 添加共享文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/share_files")
async def get_share_files():
    """
    获取共享文件列表
    """
    return {"files": list(pending_downloads.values())}


@app.post("/send_to_phone")
async def send_to_phone(file_path: str = Form(...)):
    """
    反向空投：添加文件到下载队列（命令行工具使用）
    """
    try:
        source_path = Path(file_path)
        
        if not source_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 生成唯一下载ID
        download_id = str(uuid.uuid4())
        
        # 复制文件到发送目录
        dest_path = SEND_DIR / source_path.name
        counter = 1
        while dest_path.exists():
            stem = source_path.stem
            suffix = source_path.suffix
            dest_path = SEND_DIR / f"{stem}_{counter}{suffix}"
            counter += 1
        
        # 复制文件
        import shutil
        shutil.copy2(source_path, dest_path)
        
        # 添加到待下载队列
        pending_downloads[download_id] = {
            "id": download_id,
            "filename": dest_path.name,
            "path": str(dest_path),
            "size": dest_path.stat().st_size,
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"📤 已添加到发送队列: {source_path.name}")
        
        return {
            "status": "success",
            "download_id": download_id,
            "filename": dest_path.name
        }
    
    except Exception as e:
        print(f"❌ 添加发送失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pending_downloads")
async def get_pending_downloads():
    """
    获取待下载文件列表（兼容旧接口）
    """
    return {"files": list(pending_downloads.values())}


@app.get("/download/{download_id}")
async def download_file(download_id: str):
    """
    下载文件接口
    """
    if download_id not in pending_downloads:
        raise HTTPException(status_code=404, detail="下载链接不存在或已过期")
    
    file_info = pending_downloads[download_id]
    file_path = Path(file_info["path"])
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return FileResponse(
        path=file_path,
        filename=file_info["filename"],
        media_type="application/octet-stream"
    )


@app.delete("/download/{download_id}")
async def remove_download(download_id: str):
    """
    删除下载任务
    """
    if download_id in pending_downloads:
        file_info = pending_downloads[download_id]
        file_path = Path(file_info["path"])
        
        # 删除文件
        if file_path.exists():
            file_path.unlink()
        
        # 从队列移除
        del pending_downloads[download_id]
        
        return {"status": "success", "message": "已删除"}
    else:
        raise HTTPException(status_code=404, detail="下载任务不存在")


@app.get("/stats")
async def get_stats():
    """获取统计信息"""
    total_files = 0
    total_size = 0
    
    for file_path in UPLOAD_DIR.rglob("*"):
        if file_path.is_file():
            total_files += 1
            total_size += file_path.stat().st_size
    
    return {
        "total_files": total_files,
        "total_size": total_size,
        "total_size_mb": round(total_size / 1024 / 1024, 2),
        "upload_dir": str(UPLOAD_DIR.absolute()),
        "pending_downloads": len(pending_downloads)
    }


# ==================== Socket.IO 事件处理 ====================

@sio.event
async def connect(sid, environ):
    """客户端连接"""
    print(f"🔗 客户端连接: {sid}")


@sio.event
async def disconnect(sid):
    """客户端断开"""
    print(f"❌ 客户端断开: {sid}")


@sio.event
async def request_clipboard_history(sid):
    """客户端请求剪贴板历史"""
    await sio.emit('clipboard_history', clipboard_history, room=sid)


# ==================== 剪贴板监听 ====================



@app.get("/clipboard/history")
async def get_clipboard_history():
    """获取剪贴板历史"""
    return {"history": clipboard_history}


def open_browser(url: str, delay: float = 2.5):
    """延迟打开浏览器"""
    def _open():
        time.sleep(delay)
        print(f"💻 正在自动打开浏览器...\n")
        webbrowser.open(url)
    
    thread = threading.Thread(target=_open, daemon=True)
    thread.start()


def clipboard_monitor_thread():
    """在后台线程中运行剪贴板监听"""
    global last_clipboard_content
    
    print("📋 剪贴板监听已启动")
    
    while True:
        try:
            # 检查剪贴板内容
            current_content = pyperclip.paste()
            
            # 如果内容变化且不为空
            if current_content and current_content != last_clipboard_content:
                # 只同步文本内容（限制长度避免过大）
                if len(current_content) <= 10000:  # 最大10KB
                    last_clipboard_content = current_content
                    
                    # 创建剪贴板记录
                    clipboard_item = {
                        "id": str(uuid.uuid4()),
                        "content": current_content,
                        "timestamp": datetime.now().isoformat(),
                        "length": len(current_content)
                    }
                    
                    # 添加到历史（最多保留50条）
                    clipboard_history.insert(0, clipboard_item)
                    if len(clipboard_history) > 50:
                        clipboard_history.pop()
                    
                    # 使用 asyncio.run_coroutine_threadsafe 在主循环中推送
                    # 注意：这里我们直接在线程中推送，Socket.IO 会处理线程安全
                    try:
                        asyncio.run(sio.emit('clipboard_update', clipboard_item))
                    except:
                        pass  # 如果事件循环还未运行，忽略错误
                    
                    print(f"📋 剪贴板更新: {current_content[:50]}...")
            
        except Exception as e:
            print(f"❌ 剪贴板监听错误: {e}")
        
        # 每0.5秒检查一次
        time.sleep(0.5)


def start_server(host: str = None, port: int = 8000):
    """启动服务器"""
    # 获取本机IP
    if host is None:
        host = get_local_ip()
    
    url = f"http://{host}:{port}"
    
    # 打印欢迎信息
    print("\n" + "=" * 60)
    print("🚀 局域网文件空投系统 - 已启动")
    print("=" * 60)
    print(f"\n📱 手机扫描下方二维码访问上传页面：\n")
    
    # 生成并显示二维码
    generate_qrcode(url)
    
    print(f"\n🌐 或在浏览器中访问: {url}")
    print(f"📁 共享文件位置: {SEND_DIR.absolute()}")
    print(f"📋 剪贴板同步: 已启用")
    print(f"\n按 Ctrl+C 停止服务器\n")
    print("=" * 60 + "\n")
    
    # 延迟自动打开浏览器
    open_browser(url)
    
    # 在后台线程中启动剪贴板监听
    clipboard_thread = threading.Thread(target=clipboard_monitor_thread, daemon=True)
    clipboard_thread.start()
    
    # 启动服务器
    uvicorn.run(
        socket_app, 
        host=host, 
        port=port, 
        log_level="warning"
    )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="局域网文件空投系统")
    parser.add_argument("--host", type=str, default=None, help="服务器IP地址（默认自动获取）")
    parser.add_argument("--port", type=int, default=8000, help="服务器端口（默认8000）")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    
    args = parser.parse_args()
    
    # 如果用户指定了--no-browser，则禁用自动打开
    if args.no_browser:
        # 临时禁用open_browser函数
        def open_browser(url, delay=0):
            pass
    
    start_server(host=args.host, port=args.port)

