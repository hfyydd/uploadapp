import os
import shutil
import gradio as gr
from tqdm import tqdm

def create_upload_folder():
    """创建上传文件夹，如果不存在的话"""
    upload_folder = "uploads"
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    return upload_folder

def upload_file(file_obj):
    """处理文件上传，支持大文件，并显示进度"""
    if file_obj is None:
        return "请选择一个文件上传"
    
    upload_folder = create_upload_folder()
    file_path = file_obj.name
    file_name = os.path.basename(file_path)
    destination = os.path.join(upload_folder, file_name)
    
    # 获取文件大小
    file_size = os.path.getsize(file_path)
    file_size_mb = file_size / (1024 * 1024)
    
    # 创建进度条
    progress_bar = tqdm(total=file_size, unit='B', unit_scale=True, desc=f"上传 {file_name}")
    
    # 分块复制文件
    chunk_size = 1024 * 1024  # 1MB 块大小
    with open(file_path, 'rb') as src_file, open(destination, 'wb') as dst_file:
        while True:
            chunk = src_file.read(chunk_size)
            if not chunk:
                break
            dst_file.write(chunk)
            progress_bar.update(len(chunk))
    
    progress_bar.close()
    
    return f"文件 '{file_name}' ({file_size_mb:.2f} MB) 上传成功！存储在 {destination}"

def list_uploaded_files():
    """列出已上传的文件"""
    upload_folder = "uploads"
    if not os.path.exists(upload_folder):
        return "上传文件夹不存在"
    
    files = os.listdir(upload_folder)
    if not files:
        return "没有上传的文件"
    
    result = "已上传的文件：\n"
    for file in files:
        file_path = os.path.join(upload_folder, file)
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # 转换为 MB
        result += f"- {file} ({file_size:.2f} MB)\n"
    
    return result

def delete_file(file_name):
    """删除已上传的文件"""
    if not file_name or file_name == "":
        return "请输入要删除的文件名"
    
    upload_folder = "uploads"
    file_path = os.path.join(upload_folder, file_name)
    
    if not os.path.exists(file_path):
        return f"文件 '{file_name}' 不存在"
    
    try:
        os.remove(file_path)
        return f"文件 '{file_name}' 已成功删除"
    except Exception as e:
        return f"删除文件时出错: {str(e)}"

# 创建 Gradio 界面
with gr.Blocks(title="大文件上传应用") as app:
    gr.Markdown("# 大文件上传应用")
    
    with gr.Tab("上传文件"):
        with gr.Row():
            file_input = gr.File(label="选择要上传的文件")
        
        upload_button = gr.Button("上传文件")
        upload_result = gr.Textbox(label="上传结果", lines=3)
        
        upload_button.click(
            fn=upload_file,
            inputs=[file_input],
            outputs=[upload_result]
        )
    
    with gr.Tab("管理文件"):
        with gr.Row():
            refresh_button = gr.Button("刷新文件列表")
        
        files_list = gr.Textbox(label="已上传的文件", lines=10)
        
        with gr.Row():
            delete_file_name = gr.Textbox(label="输入要删除的文件名")
            delete_button = gr.Button("删除文件")
        
        delete_result = gr.Textbox(label="删除结果")
        
        refresh_button.click(
            fn=list_uploaded_files,
            inputs=[],
            outputs=[files_list]
        )
        
        delete_button.click(
            fn=delete_file,
            inputs=[delete_file_name],
            outputs=[delete_result]
        )

# 启动应用
if __name__ == "__main__":
    # 确保上传文件夹存在
    create_upload_folder()
    # 启动Gradio应用
    app.launch() 