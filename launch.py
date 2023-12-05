import gradio as gr
import time
import sys
import torch

# 获取GPU信息
def get_gpu_info():
    print(torch.__version__)
    gpu_info = ["CPU"]  # 默认至少有一个 CPU 选项
    try:
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_info.extend([torch.cuda.get_device_name(i) for i in range(gpu_count)])
    except Exception as e:
        pass
    return gpu_info

# 获取可用的GPU列表
available_gpus = get_gpu_info()

# 模拟可选的模型列表
available_models = ["Model A", "Model B", "Model C"]

available_languages = ["中文", "English"]

def upload_and_process_file(input_file, target_column, start_row, end_row, original_language, target_language, selected_gpu, selected_model):
    # 获取文件名和内容
    file_name = input_file.name
    with open(file_name, 'r', encoding='utf-8') as f:
        file_content = f.read()

    # 模拟处理文件的过程
    total_steps = 10
    for step in range(total_steps):
        # 模拟处理每一步，实际情况中你需要替换成真实的文件处理逻辑
        time.sleep(1)
        
        # 更新进度条和日志输出到控制台
        progress = (step + 1) / total_steps
        log_message = f"正在处理步骤 {step + 1}/{total_steps}"
        sys.stdout.write(f"\r{log_message}")
        sys.stdout.flush()

    # 处理完成后返回结果
    result = f"\n文件 '{file_name}' 处理完成，内容为:\n{file_content}\n"
    result += f"目标列: {target_column}\n起始行: {start_row}\n终止行: {end_row}\n"
    result += f"原始语言：{original_language}\n目标语言: {target_language}\n"
    result += f"选择的GPU: {selected_gpu}\n选择的模型: {selected_model}"
    return result

# iface = gr.Interface(
#     fn=upload_and_process_file,
#     inputs=[
#         "file",
#         gr.Textbox(label="目标列"),
#         gr.Number(value=1, label="起始行"),
#         gr.Number(value=10, label="终止行"),
#         gr.Dropdown(choices=available_languages, label="原始语言", value=available_languages[0]),
#         gr.Dropdown(choices=available_languages, label="目标语言", value=available_languages[1]),
#         gr.Dropdown(choices=available_gpus, label="选择GPU", value=available_gpus[0]),
#         gr.Dropdown(choices=available_models, label="选择模型", value=available_models[0]),
#     ],
#     outputs="text"
# )
# iface.launch()

with gr.Blocks() as interface:
    with gr.Row():
        with gr.Column():
            input_file = gr.File()
            with gr.Row():
                target_column = gr.Textbox(label="目标列")
                start_row = gr.Number(value=1, label="起始行")
                end_row = gr.Number(value=10, label="终止行")
            with gr.Row():
                original_language = gr.Dropdown(choices=available_languages, label="原始语言", value=available_languages[0])
                target_language = gr.Dropdown(choices=available_languages, label="目标语言", value=available_languages[1])
            with gr.Row():
                selected_gpu = gr.Dropdown(choices=available_gpus, label="选择GPU", value=available_gpus[0])
                selected_model = gr.Dropdown(choices=available_models, label="选择模型", value=available_models[0])
            translate_button = gr.Button("Translate")
        with gr.Column():
            # Define the output block using the output method
            output_text = gr.DataFrame(value=[["Suit", 5000], ["Laptop", 800], ["Car", 1800]], headers=["name", "age"])
    
    # Use the output block as the output for the click method
    translate_button.click(upload_and_process_file, inputs=[input_file, target_column, start_row, end_row, original_language, target_language, selected_gpu, selected_model], outputs=output_text)

interface.launch()


