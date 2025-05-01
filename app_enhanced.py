import os
import time
import shutil
import gradio as gr
from tqdm import tqdm
import datetime
import math
import threading
import json

# 配置选项
UPLOAD_FOLDER = "uploads"
MAX_DISPLAY_FILES = 50  # 最多显示的文件数
ALLOWED_EXTENSIONS = None  # 设置为None允许所有文件类型，或指定列表如 ['.pdf', '.txt', '.jpg']
CHUNK_SIZE = 4 * 1024 * 1024  # 4MB 块大小，增大块大小以加快上传

# 全局变量用于存储上传状态
upload_status_dict = {
    "status": "就绪",
    "progress": 0,
    "message": "未开始上传",
    "current_file": "",
    "total_files": 0,
    "transferred": "0 MB",
    "total_size": "0 MB",
    "speed": "0 MB/s",
    "eta": "0秒"
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

def is_allowed_file(filename):
    """检查文件是否允许上传"""
    if ALLOWED_EXTENSIONS is None:
        return True
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

def update_upload_status():
    """返回当前上传状态的格式化字符串"""
    status = upload_status_dict["status"]
    progress = upload_status_dict["progress"]
    message = upload_status_dict["message"]
    
    progress_html = f"""
    <div style="margin-bottom: 10px;">
        <div style="width: 100%; background-color: #f0f0f0; border-radius: 5px; height: 30px; overflow: hidden;">
            <div style="width: {progress}%; height: 100%; background-color: #4CAF50; 
                 text-align: center; line-height: 30px; color: white;">
                {progress}%
            </div>
        </div>
    </div>
    <div>
        <p><b>状态:</b> {status}</p>
        <p><b>文件:</b> {upload_status_dict["current_file"]}</p>
        <p><b>进度:</b> {upload_status_dict["transferred"]} / {upload_status_dict["total_size"]}</p>
        <p><b>速度:</b> {upload_status_dict["speed"]}</p>
        <p><b>剩余时间:</b> {upload_status_dict["eta"]}</p>
        <p><b>详情:</b> {message}</p>
    </div>
    """
    return progress_html

def upload_file(files):
    """处理多文件上传，支持大文件，并显示进度"""
    global upload_status_dict
    
    if not files:
        return "请选择至少一个文件上传", None, update_upload_status()
    
    # 创建变量保存结果，以便线程可以更新
    result_update = "上传中..."
    storage_update = None
    
    # 创建一个线程来处理上传，这样不会阻塞UI
    def upload_thread():
        global upload_status_dict
        nonlocal result_update
        nonlocal storage_update
        
        try:
            create_upload_folder()
            
            results = []
            total_size = 0
            file_count = len(files)
            
            # 计算总大小
            for file_obj in files:
                file_size = os.path.getsize(file_obj.name)
                total_size += file_size
            
            # 更新状态字典
            upload_status_dict = {
                "status": "准备中",
                "progress": 0,
                "message": f"准备上传 {file_count} 个文件, 总大小: {format_size(total_size)}...",
                "current_file": "准备中...",
                "total_files": file_count,
                "transferred": "0 B",
                "total_size": format_size(total_size),
                "speed": "0 B/s",
                "eta": "计算中..."
            }
            
            # 上传文件
            total_transferred = 0
            total_start_time = time.time()
            
            for i, file_obj in enumerate(files):
                file_path = file_obj.name
                file_name = os.path.basename(file_path)
                
                upload_status_dict["current_file"] = f"{i+1}/{file_count}: {file_name}"
                upload_status_dict["status"] = "上传中"
                
                if not is_allowed_file(file_name):
                    results.append(f"文件 '{file_name}' 类型不被允许")
                    continue
                    
                destination = os.path.join(UPLOAD_FOLDER, file_name)
                
                # 如果文件已存在，添加时间戳
                if os.path.exists(destination):
                    name, ext = os.path.splitext(file_name)
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_name = f"{name}_{timestamp}{ext}"
                    destination = os.path.join(UPLOAD_FOLDER, file_name)
                    upload_status_dict["current_file"] = f"{i+1}/{file_count}: {file_name}"
                
                file_size = os.path.getsize(file_path)
                file_start_time = time.time()
                
                # 分块复制文件
                transferred = 0
                last_update_time = time.time()
                
                with open(file_path, 'rb') as src_file, open(destination, 'wb') as dst_file:
                    while True:
                        chunk = src_file.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        dst_file.write(chunk)
                        chunk_size = len(chunk)
                        transferred += chunk_size
                        total_transferred += chunk_size
                        
                        # 计算进度百分比
                        file_progress = int((transferred / file_size) * 100)
                        total_progress = int((total_transferred / total_size) * 100)
                        
                        # 计算速度和剩余时间
                        current_time = time.time()
                        time_diff = current_time - last_update_time
                        
                        if time_diff > 0.3:  # 每0.3秒更新一次状态
                            speed = chunk_size / time_diff
                            avg_speed = transferred / (current_time - file_start_time)
                            last_update_time = current_time
                            
                            # 估计剩余时间
                            if avg_speed > 0:
                                remaining_bytes = file_size - transferred
                                eta_seconds = remaining_bytes / avg_speed
                                
                                # 更新状态字典
                                upload_status_dict["progress"] = total_progress
                                upload_status_dict["transferred"] = format_size(transferred)
                                upload_status_dict["speed"] = format_size(avg_speed) + "/s"
                                upload_status_dict["eta"] = format_time(eta_seconds)
                                upload_status_dict["message"] = (
                                    f"文件: {file_progress}% | " +
                                    f"总进度: {total_progress}% | " +
                                    f"速度: {format_size(avg_speed)}/s"
                                )
                        
                        # 防止占用过多CPU
                        time.sleep(0.01)
                
                # 计算文件上传时间
                file_upload_time = time.time() - file_start_time
                avg_speed = file_size / file_upload_time if file_upload_time > 0 else 0
                
                results.append(
                    f"文件 '{file_name}' ({format_size(file_size)}) 上传成功 - " +
                    f"用时: {format_time(file_upload_time)}, 平均速度: {format_size(avg_speed)}/s"
                )
                
                # 更新完成一个文件的状态
                upload_status_dict["message"] = f"已完成: {i+1}/{file_count} 个文件"
            
            # 计算总上传时间
            total_upload_time = time.time() - total_start_time
            avg_total_speed = total_size / total_upload_time if total_upload_time > 0 else 0
            
            # 更新完成状态
            upload_status_dict = {
                "status": "完成",
                "progress": 100,
                "message": f"全部完成! 总用时: {format_time(total_upload_time)}, 平均速度: {format_size(avg_total_speed)}/s",
                "current_file": "全部文件",
                "total_files": file_count,
                "transferred": format_size(total_size),
                "total_size": format_size(total_size),
                "speed": format_size(avg_total_speed) + "/s",
                "eta": "0秒"
            }
            
            # 更新存储统计
            file_count_str, total_size_str, _ = get_upload_info()
            result_update = "\n".join(results)
            storage_update = f"存储空间: {file_count_str}, 总大小: {total_size_str}"
            
        except Exception as e:
            upload_status_dict = {
                "status": "错误",
                "progress": 0,
                "message": f"上传出错: {str(e)}",
                "current_file": "",
                "total_files": 0,
                "transferred": "0 B",
                "total_size": "0 B",
                "speed": "0 B/s",
                "eta": "0秒"
            }
            result_update = f"上传出错: {str(e)}"
    
    # 初始化显示
    upload_status_dict = {
        "status": "准备中",
        "progress": 0,
        "message": "正在准备上传...",
        "current_file": "",
        "total_files": len(files),
        "transferred": "0 B",
        "total_size": "计算中...",
        "speed": "0 B/s",
        "eta": "计算中..."
    }
    
    # 启动上传线程
    thread = threading.Thread(target=upload_thread)
    thread.daemon = True
    thread.start()
    
    # 返回初始状态
    return result_update, storage_update, update_upload_status()

def list_uploaded_files():
    """列出已上传的文件"""
    if not os.path.exists(UPLOAD_FOLDER):
        return "上传文件夹不存在", [], None
    
    files = os.listdir(UPLOAD_FOLDER)
    if not files:
        return "没有上传的文件", [], None
    
    # 按修改时间排序文件（最新的在前）
    files.sort(key=lambda x: os.path.getmtime(os.path.join(UPLOAD_FOLDER, x)), reverse=True)
    
    # 限制显示数量
    if len(files) > MAX_DISPLAY_FILES:
        files = files[:MAX_DISPLAY_FILES]
    
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
    
    return f"显示 {len(file_list)} 个文件 (共 {file_count})", file_list, f"存储空间: {file_count}, 总大小: {total_size}"

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
with gr.Blocks(title="大文件上传应用", theme=gr.themes.Soft(primary_hue="blue"), css="body {overflow-y: scroll;}") as app:
    gr.Markdown("# 📁 大文件上传应用")
    gr.Markdown("支持上传大文件，包括 15GB 以上的文件，上传过程中请勿关闭窗口")
    
    # 创建全局变量存储上传状态
    is_uploading = gr.State(False)
    
    with gr.Tab("📤 上传文件"):
        with gr.Row():
            with gr.Column(scale=3):
                file_input = gr.File(label="选择要上传的文件", file_count="multiple")
            with gr.Column(scale=1):
                storage_info = gr.Textbox(label="存储统计", value="存储空间: 0 个文件, 总大小: 0 B")
        
        # 添加明显的进度状态区域
        upload_status = gr.Textbox(label="上传状态", value="准备就绪，请选择文件并点击上传按钮", lines=1)
        
        # 使用更醒目的按钮
        upload_button = gr.Button("📤 开始上传", variant="primary", size="lg")
        
        # 使用HTML显示自定义进度条和详细信息
        progress_html = gr.HTML(update_upload_status())
        
        upload_result = gr.Textbox(label="上传结果", lines=5)
        
        # 更新存储信息
        file_count, total_size, _ = get_upload_info()
        storage_info.value = f"存储空间: {file_count}, 总大小: {total_size}"
        
        # 辅助函数用于更新UI
        def update_ui():
            return upload_status_dict["message"], update_upload_status()
        
        # 辅助函数用于开始上传
        def start_upload(files):
            """开始上传并标记为上传中"""
            if not files:
                return False, "请选择至少一个文件上传", None, update_upload_status()
            
            # 设置正在上传标志
            return True, "开始处理上传...", None, update_upload_status()
        
        # 辅助函数用于更新进度
        def update_progress(is_uploading_state):
            """周期性更新进度显示"""
            if is_uploading_state:
                return upload_status_dict["message"], update_upload_status()
            return gr.skip(), gr.skip()
        
        # 上传文件并处理结果
        upload_button.click(
            fn=start_upload,
            inputs=[file_input],
            outputs=[is_uploading, upload_status, upload_result, progress_html]
        ).then(
            fn=upload_file,
            inputs=[file_input],
            outputs=[upload_result, storage_info, progress_html]
        ).then(
            fn=lambda: (False,),  # 上传完成后，重置上传状态
            inputs=[],
            outputs=[is_uploading]
        )
        
        # 添加周期性更新
        app.load(
            fn=update_progress,
            inputs=[is_uploading],
            outputs=[upload_status, progress_html],
            every=0.5  # 每0.5秒更新一次
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
    # 启动Gradio应用 - 增加队列以确保进度条正常工作
    app.queue(
        concurrency_count=1,   # 每次只处理1个请求，避免多个上传冲突 
        max_size=20,           # 最多排队20个请求
    ).launch(
        share=False,           # 不共享到公共URL
        server_name="0.0.0.0", # 允许本地网络访问
        server_port=7860,      # 指定端口
        quiet=True,            # 减少日志输出
        show_api=False,        # 不显示API文档
        show_error=True,       # 显示详细错误信息
        favicon_path=None,     # 不设置图标
        allowed_paths=["uploads"], # 允许访问的路径
    ) 