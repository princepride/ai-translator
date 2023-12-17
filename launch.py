from modules import initialize
initialize.imports()

def webui():
    import time
    import sys
    import pandas as pd
    import torch
    import gradio as gr
    def get_gpu_info():
        print(torch.__version__)
        gpu_info = ["CPU"]
        try:
            if torch.cuda.is_available():
                gpu_count = torch.cuda.device_count()
                gpu_info.extend([torch.cuda.get_device_name(i) for i in range(gpu_count)])
        except Exception as e:
            pass
        return gpu_info
    available_gpus = get_gpu_info()

    available_models = ["Model A", "Model B", "Model C"]

    available_languages = ["中文", "English"]

    def upload_and_process_file(input_file, target_column, start_index, start_row, end_row, original_language, target_language, selected_gpu, selected_model):
        file_name = input_file.name
        with open(file_name, 'r', encoding='utf-8') as f:
            file_content = f.read()

        total_steps = 2
        for step in range(total_steps):
            time.sleep(1)
            log_message = f"正在处理步骤 {step + 1}/{total_steps}"
            sys.stdout.write(f"\r{log_message}")
            sys.stdout.flush()

        result = f"\n文件 '{file_name}' 处理完成，内容为:\n{file_content}\n"
        result += f"目标列: {target_column}\n起始行: {start_row}\n终止行: {end_row}\n"
        result += f"原始语言：{original_language}\n目标语言: {target_language}\n"
        result += f"选择的GPU: {selected_gpu}\n选择的模型: {selected_model}"
        return {"value":[["文件",file_name],["选择的模型",selected_model]], "header":["parameter", "value"]}

    with gr.Blocks() as interface:
        with gr.Tabs():
            with gr.TabItem("Excel Translator"):
                with gr.Row():
                    with gr.Column():
                        input_file = gr.File()
                        with gr.Row():
                            target_column = gr.Textbox(value="E", label="目标列")
                            start_index = gr.Number(value=1, label="起始编号")
                            start_row = gr.Number(value=1, label="起始行")
                            end_row = gr.Number(value=10, label="终止行")
                        with gr.Row():
                            original_language = gr.Dropdown(choices=available_languages, label="原始语言", value=available_languages[0])
                            target_language = gr.Dropdown(choices=available_languages, label="目标语言", value=available_languages[1])
                        with gr.Row():
                            selected_gpu = gr.Dropdown(choices=available_gpus, label="选择GPU", value=available_gpus[0])
                            selected_model = gr.Dropdown(choices=available_models, label="选择基模型", value=available_models[0])
                            selected_model = gr.Dropdown(choices=available_models, label="选择Lora模型", value=available_models[0])
                        translate_button = gr.Button("Translate")
                    with gr.Column():
                        output_text = gr.DataFrame()
                translate_button.click(upload_and_process_file, inputs=[input_file, target_column, start_index, start_row, end_row, original_language, target_language, selected_gpu, selected_model], outputs=output_text)
            with gr.TabItem("Text Translator"):
                with gr.Row():
                    with gr.Column():
                        gr.Textbox(label="输入文本")
                        with gr.Row():
                            original_language = gr.Dropdown(choices=available_languages, label="原始语言", value=available_languages[0])
                            target_language = gr.Dropdown(choices=available_languages, label="目标语言", value=available_languages[1])
                        with gr.Row():
                            selected_gpu = gr.Dropdown(choices=available_gpus, label="选择GPU", value=available_gpus[0])
                            selected_model = gr.Dropdown(choices=available_models, label="选择基模型", value=available_models[0])
                            selected_model = gr.Dropdown(choices=available_models, label="选择Lora模型", value=available_models[0])
                        translate_button = gr.Button("Translate")
                    with gr.Column():
                        gr.Textbox(label="输出文本")
    interface.launch()

if __name__ == "__main__":
    webui()