import os
import time
import shutil
import gradio as gr
from tqdm import tqdm
import datetime

# 配置选项
UPLOAD_FOLDER = "uploads"
MAX_DISPLAY_FILES = 50  # 最多显示的文件数
ALLOWED_EXTENSIONS = None  # 设置为None允许所有文件类型，或指定列表如 ['.pdf', '.txt', '.jpg']

def format_size(size_bytes):
    """将字节数格式化为人类可读的形式"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0 or unit == 'TB':
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0

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

def upload_file(files, progress=gr.Progress()):
    """处理多文件上传，支持大文件，并显示进度"""
    if not files:
        return "请选择至少一个文件上传", None
    
    create_upload_folder()
    
    results = []
    total_size = 0
    file_count = len(files)
    
    # 计算总大小
    for file_obj in files:
        file_size = os.path.getsize(file_obj.name)
        total_size += file_size
    
    progress(0, desc=f"准备上传 {file_count} 个文件...")
    
    # 上传文件
    current_progress = 0
    for i, file_obj in enumerate(files):
        file_path = file_obj.name
        file_name = os.path.basename(file_path)
        
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
        
        file_size = os.path.getsize(file_path)
        
        # 分块复制文件
        chunk_size = 1024 * 1024  # 1MB 块大小
        transferred = 0
        
        with open(file_path, 'rb') as src_file, open(destination, 'wb') as dst_file:
            while True:
                chunk = src_file.read(chunk_size)
                if not chunk:
                    break
                dst_file.write(chunk)
                transferred += len(chunk)
                current_progress += len(chunk) / total_size
                progress(min(0.99, current_progress), 
                         desc=f"上传 {i+1}/{file_count}: {file_name} ({format_size(transferred)}/{format_size(file_size)})")
                time.sleep(0.01)  # 给UI更新的时间
        
        results.append(f"文件 '{file_name}' ({format_size(file_size)}) 上传成功")
    
    progress(1.0, desc="上传完成!")
    
    # 更新文件列表和存储统计
    file_count, total_size, _ = get_upload_info()
    
    return "\n".join(results), f"存储空间: {file_count}, 总大小: {total_size}"

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
with gr.Blocks(title="大文件上传应用") as app:
    gr.Markdown("# 📁 大文件上传应用")
    
    with gr.Tab("📤 上传文件"):
        with gr.Row():
            with gr.Column(scale=3):
                file_input = gr.File(label="选择要上传的文件", file_count="multiple")
            with gr.Column(scale=1):
                storage_info = gr.Textbox(label="存储统计", value="存储空间: 0 个文件, 总大小: 0 B")
        
        upload_button = gr.Button("📤 上传文件", variant="primary")
        upload_result = gr.Textbox(label="上传结果", lines=5)
        
        # 更新存储信息
        file_count, total_size, _ = get_upload_info()
        storage_info.value = f"存储空间: {file_count}, 总大小: {total_size}"
        
        upload_button.click(
            fn=upload_file,
            inputs=[file_input],
            outputs=[upload_result, storage_info]
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
    app.launch() 