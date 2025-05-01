import os
import time
import shutil
import gradio as gr
import datetime
import threading

# 配置选项
UPLOAD_FOLDER = "uploads"
CHUNK_SIZE = 8 * 1024 * 1024  # 8MB 块大小，加快上传速度
REFRESH_INTERVAL = 0.5  # 进度刷新间隔（秒）

# 全局变量来存储进度信息
upload_progress = {
    "is_uploading": False,
    "file_name": "",
    "file_progress": 0,
    "total_progress": 0,
    "current_file": 0,
    "total_files": 0,
    "speed": "0 MB/s",
    "started_at": 0,
    "last_update": 0,
    "transferred": 0,
    "total_size": 0,
    "message": "未开始上传"
}

def format_size(size_bytes):
    """将字节数格式化为人类可读的形式"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0 or unit == 'TB':
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0

def format_time(seconds):
    """格式化时间为人类可读形式"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}分钟"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}小时"

def create_upload_folder():
    """创建上传文件夹，如果不存在的话"""
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    return UPLOAD_FOLDER

def get_upload_info():
    """获取上传文件夹信息"""
    if not os.path.exists(UPLOAD_FOLDER):
        return "0 个文件", "0 B", []
    
    files = os.listdir(UPLOAD_FOLDER)
    total_size = sum(os.path.getsize(os.path.join(UPLOAD_FOLDER, f)) for f in files)
    
    return f"{len(files)} 个文件", format_size(total_size), files

def get_progress_status():
    """获取当前上传进度状态"""
    global upload_progress
    
    if not upload_progress["is_uploading"]:
        return "准备就绪，请选择文件并点击上传按钮"
    
    file_name = upload_progress["file_name"]
    file_progress = upload_progress["file_progress"]
    total_progress = upload_progress["total_progress"]
    current_file = upload_progress["current_file"]
    total_files = upload_progress["total_files"]
    speed = upload_progress["speed"]
    
    # 计算估计剩余时间
    if upload_progress["transferred"] > 0 and time.time() - upload_progress["started_at"] > 0:
        avg_speed = upload_progress["transferred"] / (time.time() - upload_progress["started_at"])
        remaining_bytes = upload_progress["total_size"] - upload_progress["transferred"]
        if avg_speed > 0:
            eta = remaining_bytes / avg_speed
            eta_text = format_time(eta)
        else:
            eta_text = "计算中..."
    else:
        eta_text = "计算中..."
    
    status = (
        f"上传中：{current_file}/{total_files} - {file_name}\n"
        f"文件进度：{file_progress}% | 总进度：{total_progress}%\n"
        f"传输速度：{speed} | 预计剩余时间：{eta_text}"
    )
    return status

def update_progress_in_background():
    """后台线程定期更新进度状态"""
    global upload_progress
    
    while upload_progress["is_uploading"]:
        # 计算距离上次更新的时间
        current_time = time.time()
        time_diff = current_time - upload_progress["last_update"]
        
        if time_diff > 0:
            transferred_diff = upload_progress["transferred"] - upload_progress.get("last_transferred", 0)
            
            # 计算传输速度 (bytes/sec)
            if time_diff > 0:
                speed_bytes = transferred_diff / time_diff
                upload_progress["speed"] = f"{format_size(speed_bytes)}/s"
            
            # 存储本次的传输量用于下次计算
            upload_progress["last_transferred"] = upload_progress["transferred"]
            upload_progress["last_update"] = current_time
        
        time.sleep(REFRESH_INTERVAL)

def upload_file_background(files, status_callback=None):
    """在后台线程执行文件上传，并通过回调函数更新状态"""
    global upload_progress
    
    results = []
    
    try:
        if not files:
            return "请选择至少一个文件上传", None
        
        create_upload_folder()
        
        upload_progress["is_uploading"] = True
        upload_progress["started_at"] = time.time()
        upload_progress["last_update"] = time.time()
        upload_progress["transferred"] = 0
        upload_progress["total_size"] = 0
        upload_progress["total_files"] = len(files)
        upload_progress["current_file"] = 0
        
        # 计算总大小
        for file_obj in files:
            file_size = os.path.getsize(file_obj.name)
            upload_progress["total_size"] += file_size
        
        upload_progress["message"] = f"准备上传 {len(files)} 个文件, 总大小: {format_size(upload_progress['total_size'])}..."
        
        # 启动进度更新线程
        progress_thread = threading.Thread(target=update_progress_in_background)
        progress_thread.daemon = True
        progress_thread.start()
        
        # 开始上传文件
        for i, file_obj in enumerate(files):
            upload_progress["current_file"] = i + 1
            file_path = file_obj.name
            file_name = os.path.basename(file_path)
            upload_progress["file_name"] = file_name
            
            destination = os.path.join(UPLOAD_FOLDER, file_name)
            
            # 如果文件已存在，添加时间戳
            if os.path.exists(destination):
                name, ext = os.path.splitext(file_name)
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                file_name = f"{name}_{timestamp}{ext}"
                destination = os.path.join(UPLOAD_FOLDER, file_name)
                upload_progress["file_name"] = file_name
            
            file_size = os.path.getsize(file_path)
            file_transferred = 0
            
            # 分块复制文件
            with open(file_path, 'rb') as src_file, open(destination, 'wb') as dst_file:
                while True:
                    chunk = src_file.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    
                    dst_file.write(chunk)
                    chunk_size = len(chunk)
                    file_transferred += chunk_size
                    upload_progress["transferred"] += chunk_size
                    
                    # 更新进度百分比
                    upload_progress["file_progress"] = int((file_transferred / file_size) * 100)
                    upload_progress["total_progress"] = int((upload_progress["transferred"] / upload_progress["total_size"]) * 100)
                    
                    # 适当睡眠以减轻CPU负担
                    time.sleep(0.01)
            
            results.append(f"文件 '{file_name}' ({format_size(file_size)}) 上传成功")
        
        # 完成后更新状态
        upload_progress["file_progress"] = 100
        upload_progress["total_progress"] = 100
        
        # 更新文件列表和存储统计
        file_count, total_size, _ = get_upload_info()
        result_text = "\n".join(results)
        storage_text = f"存储空间: {file_count}, 总大小: {total_size}"
        
        # 标记上传完成
        upload_progress["is_uploading"] = False
        upload_progress["message"] = "上传完成"
        
        # 返回结果
        return result_text, storage_text
    
    except Exception as e:
        # 出错时更新状态
        upload_progress["is_uploading"] = False
        upload_progress["message"] = f"上传出错: {str(e)}"
        return f"上传出错: {str(e)}", None

def upload_file(files, progress=gr.Progress()):
    """处理文件上传，启动后台线程执行实际上传任务"""
    global upload_progress
    
    if not files:
        return "请选择至少一个文件上传", None
    
    # 重置进度信息
    upload_progress = {
        "is_uploading": True,
        "file_name": "准备中...",
        "file_progress": 0,
        "total_progress": 0,
        "current_file": 0,
        "total_files": len(files),
        "speed": "计算中...",
        "started_at": time.time(),
        "last_update": time.time(),
        "transferred": 0,
        "total_size": 0,
        "message": "正在准备上传..."
    }
    
    # 创建一个线程来处理上传
    upload_thread = threading.Thread(
        target=upload_file_background,
        args=(files,)
    )
    upload_thread.daemon = True
    upload_thread.start()
    
    # 返回初始状态，UI将通过定时更新刷新
    return "上传已开始，请耐心等待...", None

def list_uploaded_files():
    """列出已上传的文件"""
    if not os.path.exists(UPLOAD_FOLDER):
        return "上传文件夹不存在", [], None
    
    files = os.listdir(UPLOAD_FOLDER)
    if not files:
        return "没有上传的文件", [], None
    
    # 按修改时间排序文件（最新的在前）
    files.sort(key=lambda x: os.path.getmtime(os.path.join(UPLOAD_FOLDER, x)), reverse=True)
    
    file_list = []
    for file in files:
        file_path = os.path.join(UPLOAD_FOLDER, file)
        file_size = os.path.getsize(file_path)
        mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
        file_list.append({
            "文件名": file,
            "大小": format_size(file_size),
            "上传时间": mod_time.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    file_count, total_size, _ = get_upload_info()
    
    return f"显示 {len(file_list)} 个文件", file_list, f"存储空间: {file_count}, 总大小: {total_size}"

def delete_file(file_name):
    """删除已上传的文件"""
    if not file_name or file_name == "":
        return "请输入要删除的文件名", None
    
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    
    if not os.path.exists(file_path):
        return f"文件 '{file_name}' 不存在", None
    
    try:
        file_size = format_size(os.path.getsize(file_path))
        os.remove(file_path)
        file_count, total_size, _ = get_upload_info()
        return f"文件 '{file_name}' ({file_size}) 已成功删除", f"存储空间: {file_count}, 总大小: {total_size}"
    except Exception as e:
        return f"删除文件时出错: {str(e)}", None

def delete_all_files():
    """删除所有上传的文件"""
    if not os.path.exists(UPLOAD_FOLDER):
        return "上传文件夹不存在", None
    
    try:
        files = os.listdir(UPLOAD_FOLDER)
        if not files:
            return "没有文件可删除", None
        
        file_count = len(files)
        for file in files:
            file_path = os.path.join(UPLOAD_FOLDER, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
        
        return f"已成功删除全部 {file_count} 个文件", "存储空间: 0 个文件, 总大小: 0 B"
    except Exception as e:
        return f"删除文件时出错: {str(e)}", None

# 创建 Gradio 界面
with gr.Blocks(title="大文件上传应用", css="body {overflow-y: scroll;}") as app:
    gr.Markdown("# 📁 大文件上传应用")
    gr.Markdown("支持上传大文件，包括15GB以上的文件，上传过程中请勿关闭窗口")
    
    with gr.Tab("📤 上传文件"):
        with gr.Row():
            with gr.Column(scale=3):
                file_input = gr.File(label="选择要上传的文件", file_count="multiple")
            with gr.Column(scale=1):
                storage_info = gr.Textbox(label="存储统计", value="存储空间: 0 个文件, 总大小: 0 B")
        
        upload_button = gr.Button("📤 开始上传", variant="primary")
        
        # 使用更明显的进度状态区域
        gr.Markdown("### 上传状态")
        upload_status = gr.Textbox(
            label="状态", 
            value="准备就绪，请选择文件并点击上传按钮",
            lines=4
        )
        
        upload_result = gr.Textbox(label="上传结果", lines=5)
        
        # 更新存储信息
        file_count, total_size, _ = get_upload_info()
        storage_info.value = f"存储空间: {file_count}, 总大小: {total_size}"
        
        # 定义刷新状态的函数
        def refresh_status():
            status = get_progress_status()
            return status
        
        # 添加刷新按钮代替自动刷新
        refresh_button = gr.Button("🔄 刷新上传状态")
        
        # 开始上传
        upload_button.click(
            fn=lambda: "开始上传，准备中...",
            inputs=[],
            outputs=[upload_status]
        ).then(
            fn=upload_file,
            inputs=[file_input],
            outputs=[upload_result, storage_info]
        )
        
        # 刷新按钮
        refresh_button.click(
            fn=refresh_status,
            inputs=[],
            outputs=[upload_status]
        )
    
    with gr.Tab("📋 管理文件"):
        with gr.Row():
            with gr.Column(scale=2):
                refresh_button = gr.Button("🔄 刷新文件列表")
                delete_all_button = gr.Button("🗑️ 删除所有文件", variant="stop")
            with gr.Column(scale=1):
                storage_info_manage = gr.Textbox(label="存储统计", value="存储空间: 0 个文件, 总大小: 0 B")
        
        files_status = gr.Textbox(label="状态")
        files_table = gr.Dataframe(headers=["文件名", "大小", "上传时间"], interactive=False)
        
        with gr.Row():
            delete_file_name = gr.Textbox(label="输入要删除的文件名")
            delete_button = gr.Button("🗑️ 删除文件")
        
        delete_result = gr.Textbox(label="删除结果")
        
        # 初始加载文件列表
        files_status.value, files_table.value, storage_info_manage.value = list_uploaded_files()
        
        refresh_button.click(
            fn=list_uploaded_files,
            inputs=[],
            outputs=[files_status, files_table, storage_info_manage]
        )
        
        delete_button.click(
            fn=delete_file,
            inputs=[delete_file_name],
            outputs=[delete_result, storage_info_manage]
        ).then(
            fn=list_uploaded_files,
            inputs=[],
            outputs=[files_status, files_table, storage_info_manage]
        )
        
        delete_all_button.click(
            fn=delete_all_files,
            inputs=[],
            outputs=[delete_result, storage_info_manage]
        ).then(
            fn=list_uploaded_files,
            inputs=[],
            outputs=[files_status, files_table, storage_info_manage]
        )

# 启动应用
if __name__ == "__main__":
    # 确保上传文件夹存在
    create_upload_folder()
    # 启动Gradio应用
    app.queue(max_size=10).launch(
        server_name="0.0.0.0",  # 允许本地网络访问
        server_port=7860,       # 指定端口
        # 减少日志输出
        show_api=False,         # 不显示API文档
        show_error=True         # 显示详细错误信息
    ) 