import csv
import yaml
import os
import shutil
import gradio as gr
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from utils.path import get_models
from utils.cuda import get_gpu_info
import json
import time
import importlib.util
from modules.file import FileReaderFactory, ExcelFileWriter

# 获取当前脚本所在目录的绝对路径
script_dir = os.path.dirname(os.path.abspath(__file__))

# 构建baseConfig.yml和modelExplains.yml的绝对路径
file_path = os.path.join(script_dir, 'configs', 'baseConfig.yml')

with open(file_path, 'r') as file:
    yaml_data = yaml.load(file, Loader=yaml.FullLoader)

def webui():
    available_gpus = get_gpu_info()
    api_models = get_models(os.path.join(script_dir, 'models/API'))
    local_models = get_models(os.path.join(script_dir, 'models/local'))
    available_models = {**api_models, **local_models}
    available_languages = []
    
    def update_choices(selected_model):
        model_path = available_models[selected_model]
        support_language_path = os.path.join(model_path, 'support_language.json')
        readme_path = os.path.join(model_path, 'README.md')
        model_explanation = "This model doesn't have an explanation."
        if os.path.isfile(readme_path):
            with open(readme_path, 'r', encoding='utf-8') as file:
                model_explanation = file.read()
        try:
            with open(support_language_path, 'r') as file:
                support_languages = json.load(file)
                original_language_choices = support_languages["original_language"]
                target_language_choices = support_languages["target_language"]
        except Exception as e:
            print(f"Error reading support_language.json: {e}")
            original_language_choices = []
            target_language_choices = []
        lora_list = [''] + [f for f in os.listdir(model_path) if os.path.isdir(os.path.join(model_path, f)) and not f.startswith('.') and not f.startswith('_')]
        return gr.Dropdown(choices=original_language_choices), gr.Dropdown(choices=target_language_choices), gr.Dropdown(choices=lora_list), model_explanation
    
    def translate_excel(input_file, start_row, end_row, start_column, target_column, selected_model, selected_lora_model, selected_gpu, batch_size, original_language, target_languages):
        start_time = time.time()
        file_path = input_file.name
        reader, fp = FileReaderFactory.create_reader(file_path)
        inputs = reader.extract_text(file_path, target_column, start_row, end_row)

        outputs = translate(inputs, selected_model, selected_lora_model, selected_gpu, batch_size, original_language, target_languages)

        excel_writer = ExcelFileWriter()
        print("Finally processed number: ", len(outputs))
        output_file = excel_writer.write_text(file_path, outputs, start_column, start_row, end_row)

        end_time = time.time()
        return f"Total process time: {int(end_time-start_time)}s", output_file
    
    def translate(inputs, selected_model, selected_lora_model, selected_gpu, batch_size, original_language, target_languages):
        if isinstance(inputs, str):
            inputs = [inputs]
        model_file_path = os.path.join(available_models[selected_model], 'model.py')
        # 检查文件是否存在
        if not os.path.exists(model_file_path):
            print(f"No model.py found in {available_models[selected_model]}")
            return
        spec = importlib.util.spec_from_file_location("model", model_file_path)
        model_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model_module)
        outputs = {}
        if hasattr(model_module, 'Model'):
            model = model_module.Model(available_models[selected_model], selected_lora_model, selected_gpu)
            if hasattr(model, 'generate'):
                outputs = model.generate(inputs, original_language, target_languages, batch_size)
            else:
                print("Model class does not have a 'generate' method.")
        else:
            print("No Model class found in model.py.")
        return outputs

    def translate_folder(input_folder, selected_model, selected_lora_model, selected_gpu, batch_size, original_language, target_languages):
        start_time = time.time()
        if not input_folder:
            return "No files uploaded", []

        folder_path = os.path.dirname(input_folder[0].name)
        processed_files = []

        # Create a new folder named 'processed' within the uploaded folder
        processed_folder = os.path.join(folder_path, 'processed')
        os.makedirs(processed_folder, exist_ok=True)

        for input_file in input_folder:
            file_path = input_file.name
            print(f"Processing file: {file_path}")  # Debugging output
            # Use the factory to create the appropriate file reader and possibly convert the file
            try:
                reader, updated_file_path = FileReaderFactory.create_reader(file_path)
                print(f"Updated file path: {updated_file_path}")  # Debugging output
            except ValueError as e:
                print(f"Error: {e}")
                continue

            # Ensure input_file refers to the updated file path if conversion occurred
            if file_path != updated_file_path:
                input_file.name = updated_file_path

            # Determine the number of rows and columns automatically for Excel files
            if updated_file_path.endswith('.xlsx'):
                try:
                    workbook = load_workbook(updated_file_path, read_only=True)
                    sheet = workbook.active
                    end_row = sheet.max_row
                    start_column = 'A'
                    end_column = sheet.max_column
                    target_column = start_column
                    print(f"Excel file loaded: {updated_file_path}")  # Debugging output
                except Exception as e:
                    print(f"Failed to load Excel file: {updated_file_path}. Error: {e}")
                    continue  # Skip this file if it cannot be loaded
            elif updated_file_path.endswith('.csv'):
                try:
                    with open(updated_file_path, 'r', newline='') as csvfile:
                        csv_reader = csv.reader(csvfile)
                        end_row = sum(1 for row in csv_reader)
                        csvfile.seek(0)  # Reset reader to read the file again
                        start_column = 0
                        end_column = len(next(csv_reader)) - 1  # Assuming all rows have the same number of columns
                        target_column = start_column
                        print(f"CSV file loaded: {updated_file_path}")  # Debugging output
                except Exception as e:
                    print(f"Failed to load CSV file: {updated_file_path}. Error: {e}")
                    continue
            else:
                print(f"Unsupported file type: {updated_file_path}")
                continue  # Skip unsupported file types

            # Convert end_column to a letter if dealing with an Excel file
            if updated_file_path.endswith('.xlsx'):
                end_column_letter = get_column_letter(end_column)
            else:
                end_column_letter = end_column  # For CSV, keep it as an integer

            # Translate the file content
            process_time, output_file = translate_excel(input_file, 1, end_row, start_column, end_column_letter, selected_model, selected_lora_model, selected_gpu, batch_size, original_language, target_languages)
            
            # Move the processed file to the 'processed' folder
            processed_file_path = os.path.join(processed_folder, os.path.basename(output_file))
            shutil.move(output_file, processed_file_path)
            processed_files.append(processed_file_path)

        end_time = time.time()
        return f"Total process time: {int(end_time - start_time)}s", processed_files


    with gr.Blocks(title="yonyou translator") as interface:
        with gr.Tabs():
            with gr.TabItem("Excel Translator"):
                with gr.Row():
                    with gr.Column():
                        input_file = gr.File()
                        with gr.Row():
                            start_row = gr.Number(value=yaml_data["excel_config"]["default_start_row"], label="起始行")
                            end_row = gr.Number(value=yaml_data["excel_config"]["default_end_row"], label="终止行")
                            target_column = gr.Textbox(value=yaml_data["excel_config"]["default_target_column"], label="目标列")
                            start_column = gr.Textbox(value=yaml_data["excel_config"]["default_start_column"], label="结果写入列")
                        with gr.Row():
                            selected_model = gr.Dropdown(choices=list(available_models.keys()), label="选择基模型")
                            selected_lora_model = gr.Dropdown(choices=[], label="选择Lora模型")
                            selected_gpu = gr.Dropdown(choices=available_gpus, label="选择GPU", value=available_gpus[0])
                            batch_size = gr.Number(value=10, label="批处理大小")
                        with gr.Row():
                            original_language = gr.Dropdown(choices=[], label="原始语言")
                            target_languages = gr.Dropdown(choices=[], label="目标语言", multiselect=True)
                        translate_button = gr.Button("Translate")
                    with gr.Column():
                        model_explanation_textbox = gr.Textbox(label="模型介绍", lines=5)
                        output_text = gr.Textbox(label="输出文本")
                        output_file = gr.File(label="翻译文件下载")
                selected_model.change(update_choices, inputs=[selected_model], outputs=[original_language, target_languages, selected_lora_model, model_explanation_textbox])
                translate_button.click(translate_excel, inputs=[input_file, start_row, end_row, start_column, target_column, selected_model, selected_lora_model, selected_gpu, batch_size, original_language, target_languages], outputs=[output_text, output_file])
            with gr.TabItem("Text Translator"):
                with gr.Row():
                    with gr.Column():
                        input_text = gr.Textbox(label="输入文本")
                        with gr.Row():
                            selected_model = gr.Dropdown(choices=available_models, label="选择基模型")
                            selected_lora_model = gr.Dropdown(choices=[], label="选择Lora模型")
                            selected_gpu = gr.Dropdown(choices=available_gpus, label="选择GPU", value=available_gpus[0])
                            batch_size = gr.Number(value=1, label="批处理大小", visible=False)
                        with gr.Row():
                            original_language = gr.Dropdown(choices=available_languages, label="原始语言")
                            target_languages = gr.Dropdown(choices=available_languages, label="目标语言", multiselect=True)
                        translate_button = gr.Button("Translate")
                    with gr.Column():
                        model_explanation_textbox = gr.Textbox(label="模型介绍", lines=5)
                        output_text = gr.Textbox(label="输出文本", lines=5)
                selected_model.change(update_choices, inputs=[selected_model], outputs=[original_language, target_languages, selected_lora_model, model_explanation_textbox])
                translate_button.click(translate, inputs=[input_text, selected_model, selected_lora_model, selected_gpu, batch_size, original_language, target_languages], outputs=output_text)
            # folder translator
            with gr.TabItem("Folder Translator"):
                with gr.Row():
                    with gr.Column():
                        input_folder = gr.File(file_count="directory")
                        selected_model = gr.Dropdown(choices=available_models, label="选择基模型")
                        selected_lora_model = gr.Dropdown(choices=[], label="选择Lora模型")
                        selected_gpu = gr.Dropdown(choices=available_gpus, label="选择GPU", value=available_gpus[0])
                        batch_size = gr.Number(value=1, label="批处理大小", visible=False)
                        original_language = gr.Dropdown(choices=available_languages, label="原始语言")
                        target_languages = gr.Dropdown(choices=available_languages, label="目标语言", multiselect=True)
                        translate_button = gr.Button("Translate")
                    with gr.Column():
                        model_explanation_textbox = gr.Textbox(label="模型介绍", lines=5)
                        output_text = gr.Textbox(label="输出文本", lines=5)
                        output_folder = gr.File(label="翻译文件夹下载")
                selected_model.change(update_choices, inputs=[selected_model], outputs=[original_language, target_languages, selected_lora_model, model_explanation_textbox])
                translate_button.click(translate_folder, inputs=[input_folder, selected_model, selected_lora_model, selected_gpu, batch_size, original_language, target_languages], outputs= [output_text, output_folder])
    interface.launch(share=True)
    # interface.launch(debug=True)

if __name__ == "__main__":
    webui()