from modules import initialize
import yaml
initialize.imports()

file_path = './configs/baseConfig.yml'

with open(file_path, 'r') as file:
    yaml_data = yaml.load(file, Loader=yaml.FullLoader)

# 打印读取的YAML数据
print(yaml_data['model_path']['mbart'])

def webui():
    import time
    import sys
    import torch
    import gradio as gr
    from utils.path_utils import get_folders, path_foldername_mapping
    from modules.file import FileReaderFactory
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
    model_list = []
    lora_model_list = []
    for key in yaml_data['model_path'].keys():
        if key == "lora":
            lora_model_list += get_folders(yaml_data['model_path'][key], key)
        else:
            model_list += get_folders(yaml_data['model_path'][key], key)
    print(lora_model_list)
    print(model_list)
    model_dict = path_foldername_mapping(model_list)
    print(model_dict)
    lora_model_dict = path_foldername_mapping(lora_model_list)
    available_models = list(model_dict.keys())
    print(available_models)
    available_lora_models = list(lora_model_dict.keys())
    available_languages = ["中文", "English"]

    def upload_and_process_file(input_file, target_column, start_row, end_row, original_language, target_language, selected_gpu, selected_model):
        file_path = input_file.name
        reader = FileReaderFactory.create_reader(file_path)
        texts = reader.extract_text(file_path, target_column, start_row, end_row)
        print(texts)
        return {"value":[["文件",file_path],["选择的模型",selected_model]], "header":["parameter", "value"]}

    with gr.Blocks() as interface:
        with gr.Tabs():
            with gr.TabItem("Excel Translator"):
                with gr.Row():
                    with gr.Column():
                        input_file = gr.File()
                        with gr.Row():
                            target_column = gr.Textbox(value="E", label="目标列")
                            # start_index = gr.Number(value=1, label="起始编号")
                            start_row = gr.Number(value=1, label="起始行")
                            end_row = gr.Number(value=10, label="终止行")
                        with gr.Row():
                            original_language = gr.Dropdown(choices=available_languages, label="原始语言", value=available_languages[0])
                            target_language = gr.Dropdown(choices=available_languages, label="目标语言", value=available_languages[1])
                        with gr.Row():
                            selected_gpu = gr.Dropdown(choices=available_gpus, label="选择GPU", value=available_gpus[0])
                            selected_model = gr.Dropdown(choices=available_models, label="选择基模型")
                            # selected_model = gr.Dropdown(choices=available_models, label="选择基模型")
                            selected_model = gr.Dropdown(choices=available_lora_models, label="选择Lora模型", value=available_lora_models[0] if len(available_lora_models) else "")
                        translate_button = gr.Button("Translate")
                    with gr.Column():
                        output_text = gr.DataFrame()
                # translate_button.click(upload_and_process_file, inputs=[input_file, target_column, start_index, start_row, end_row, original_language, target_language, selected_gpu, selected_model], outputs=output_text)
                translate_button.click(upload_and_process_file, inputs=[input_file, target_column, start_row, end_row, original_language, target_language, selected_gpu, selected_model], outputs=output_text)
            with gr.TabItem("Text Translator"):
                with gr.Row():
                    with gr.Column():
                        gr.Textbox(label="输入文本")
                        with gr.Row():
                            original_language = gr.Dropdown(choices=available_languages, label="原始语言", value=available_languages[0])
                            target_language = gr.Dropdown(choices=available_languages, label="目标语言", value=available_languages[1])
                        with gr.Row():
                            selected_gpu = gr.Dropdown(choices=available_gpus, label="选择GPU", value=available_gpus[0])
                            selected_model = gr.Dropdown(choices=available_models, label="选择基模型", value=available_models[0] if len(available_models) else "")
                            selected_model = gr.Dropdown(choices=available_lora_models, label="选择Lora模型", value=available_lora_models[0] if len(available_lora_models) else "")
                        translate_button = gr.Button("Translate")
                    with gr.Column():
                        gr.Textbox(label="输出文本")
    interface.launch()

if __name__ == "__main__":
    webui()