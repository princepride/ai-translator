import zipfile
from typing import Optional

import yaml
import os
import shutil
import gradio as gr
from gradio.utils import NamedString

from utils.path import get_models
from utils.cuda import get_gpu_info
import json
import time
import importlib.util
from modules.file import FileReaderFactory, ExcelFileWriter
from docx import Document
import markdown
from bs4 import BeautifulSoup
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.shared import Inches
from pptx import Presentation
import re
from transformers import AutoTokenizer

# 获取当前脚本所在目录的绝对路径
script_dir = os.path.dirname(os.path.abspath(__file__))

# 构建baseConfig.yml和modelExplains.yml的绝对路径
file_path = os.path.join(script_dir, 'configs', 'baseConfig.yml')
tokenizer = AutoTokenizer.from_pretrained(os.path.join(script_dir, 'tokenzier'))

with open(file_path, 'r') as file:
    yaml_data = yaml.load(file, Loader=yaml.FullLoader)


def update_row_selection(selected_value):
    if selected_value == "所有行":
        return gr.update(visible=False)
    else:
        return gr.update(visible=True)


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
        lora_list = [''] + [f for f in os.listdir(model_path) if
                            os.path.isdir(os.path.join(model_path, f)) and not f.startswith('.') and not f.startswith(
                                '_')]
        return gr.Dropdown(choices=original_language_choices), gr.Dropdown(
            choices=target_language_choices), gr.Dropdown(choices=lora_list), model_explanation

    def translate_excel(input_file, start_row, end_row, start_column, target_column,
                        selected_model,
                        selected_lora_model, selected_gpu, batch_size, original_language, target_languages):
        start_time = time.time()
        file_path = input_file.name
        reader, fp = FileReaderFactory.create_reader(file_path)
        inputs = reader.extract_text(file_path, target_column, start_row, end_row)

        outputs = translate(inputs, selected_model, selected_lora_model, selected_gpu, batch_size, original_language,
                            target_languages)

        excel_writer = ExcelFileWriter()
        print("Finally processed number: ", len(outputs))
        output_file = excel_writer.write_text(file_path, outputs, start_column, start_row, end_row)

        end_time = time.time()
        return f"Total process time: {int(end_time - start_time)}s", output_file

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
        outputs = []
        if hasattr(model_module, 'Model'):
            model = model_module.Model(available_models[selected_model], selected_lora_model, selected_gpu)
            if hasattr(model, 'generate'):
                outputs = model.generate(inputs, original_language, target_languages, batch_size)
            else:
                print("Model class does not have a 'generate' method.")
        else:
            print("No Model class found in model.py.")
        return outputs

    def translate_excel_folder(input_folder, start_row, end_row, start_column, target_column, selected_model,
                               selected_lora_model, selected_gpu, batch_size, original_language, target_languages,
                               row_selection):
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
            # Use factory to convert the file
            try:
                reader, updated_file_path = FileReaderFactory.create_reader(file_path)
            except ValueError as e:
                print(f"Error: {e}")
                continue

            # Ensure input_file refers to the updated file path if conversion occurred
            if file_path != updated_file_path:
                input_file.name = updated_file_path

            if row_selection == "所有行":
                end_row = FileReaderFactory.count_rows(updated_file_path)

            process_time, output_file = translate_excel(input_file, start_row, end_row, start_column, target_column,
                                                        selected_model, selected_lora_model, selected_gpu, batch_size,
                                                        original_language, target_languages)

            processed_file_path = os.path.join(processed_folder, os.path.basename(output_file))
            shutil.move(output_file, processed_file_path)
            processed_files.append(processed_file_path)

        # Create a zip file 
        zip_filename = os.path.join(folder_path, "processed_files.zip")
        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            for file in processed_files:
                zipf.write(file, os.path.basename(file))
                print(f"File {file} added to zip.")

        end_time = time.time()
        print(f"Total process time: {int(end_time - start_time)}s")
        print(f"Processed files: {processed_files}")
        return f"Total process time: {int(end_time - start_time)}s", zip_filename

    def word_to_markdown(docx_path, output_dir="images"):
        # 创建输出图片目录
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        from docx.opc.pkgreader import _SerializedRelationships, _SerializedRelationship
        from docx.opc.oxml import parse_xml

        def iter_block_items(parent):
            """
            生成文档中所有的块级元素，按顺序包括段落和表格。
            """
            parent_elm = parent.element.body
            for child in parent_elm.iterchildren():
                if child.tag == qn('w:p'):
                    yield Paragraph(child, parent)
                elif child.tag == qn('w:tbl'):
                    yield Table(child, parent)

        def load_from_xml_v2(baseURI, rels_item_xml):
            """
            Return |_SerializedRelationships| instance loaded with the
            relationships contained in *rels_item_xml*. Returns an empty
            collection if *rels_item_xml* is |None|.
            """
            srels = _SerializedRelationships()
            if rels_item_xml is not None:
                rels_elm = parse_xml(rels_item_xml)
                for rel_elm in rels_elm.Relationship_lst:
                    if rel_elm.target_ref in ('../NULL', 'NULL'):
                        continue
                    srels._srels.append(_SerializedRelationship(baseURI, rel_elm))
            return srels

        _SerializedRelationships.load_from_xml = load_from_xml_v2
        doc = Document(docx_path)
        md_content = ""

        # 用于图片计数，生成唯一的图片名称
        image_counter = 1

        for block in iter_block_items(doc):
            if isinstance(block, Paragraph):
                para = block
                # 处理图片
                for run in para.runs:
                    # 检查 run 中是否有图片
                    drawing_elements = run.element.findall(
                        './/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing')
                    for drawing in drawing_elements:
                        # 提取图片
                        blip_elements = drawing.findall(
                            './/{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
                        for blip in blip_elements:
                            rEmbed = blip.get(
                                '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                            if rEmbed and rEmbed in doc.part.related_parts:
                                image_part = doc.part.related_parts[rEmbed]
                                image_bytes = image_part.blob
                                image_name = f"image_{image_counter}.png"
                                image_path = os.path.join(output_dir, image_name)
                                with open(image_path, 'wb') as f:
                                    f.write(image_bytes)
                                # 在 Markdown 中添加图片引用
                                md_content += f"![{image_name}]({os.path.join(output_dir, image_name)})\n\n"
                                image_counter += 1
                            else:
                                print(f"Warning: Missing image resource for {rEmbed}")
                # 将标题段落转换为 Markdown 语法
                if para.style.name and para.style.name.startswith('Heading'):
                    level = int(para.style.name.split()[1])
                    md_content += f"{'#' * level} {para.text}\n\n"
                elif para.text.strip():
                    md_content += f"{para.text}\n\n"
            elif isinstance(block, Table):
                table = block
                md_content += "\n"
                # 获取表格的所有行
                rows = table.rows
                if len(rows) > 0:
                    # 生成表头
                    header_cells = rows[0].cells
                    header = "| " + " | ".join(cell.text.strip().replace('\n', ' ') for cell in header_cells) + " |\n"
                    md_content += header
                    # 添加分隔行
                    md_content += "| " + " | ".join(['---'] * len(header_cells)) + " |\n"
                    # 添加表格内容
                    for row in rows[1:]:
                        row_cells = row.cells
                        row_text = "| " + " | ".join(
                            cell.text.strip().replace('\n', ' ') for cell in row_cells) + " |\n"
                        md_content += row_text
                md_content += "\n"

        return md_content

    def markdown_to_word(md_content, word_path):
        # 将 Markdown 内容转换为 HTML，并启用表格和图片扩展
        html = markdown.markdown(md_content, extensions=['tables'])
        soup = BeautifulSoup(html, 'html.parser')
        doc = Document()

        for element in soup.contents:
            if element.name == 'h1':
                doc.add_heading(element.get_text(), level=1)
            elif element.name == 'h2':
                doc.add_heading(element.get_text(), level=2)
            elif element.name == 'h3':
                doc.add_heading(element.get_text(), level=3)
            elif element.name == 'p':
                # 检查段落中是否有图片
                if element.find('img'):
                    # 处理段落中的图片
                    for img in element.find_all('img'):
                        img_path = img.get('src')
                        alt_text = img.get('alt', '')
                        # 添加图片到文档
                        if os.path.exists(img_path):
                            try:
                                doc.add_picture(img_path, width=Inches(4))
                                # 添加图片的说明文字（可选）
                                if alt_text:
                                    last_paragraph = doc.paragraphs[-1]
                                    last_paragraph.alignment = 1  # 居中对齐
                                    doc.add_paragraph(alt_text).alignment = 1
                            except:
                                print(f"警告：处理图片时发生未知错误 {img_path}")
                        else:
                            print(f"警告：找不到图片文件 {img_path}")
                else:
                    doc.add_paragraph(element.get_text())
            elif element.name == 'ul':
                for li in element.find_all('li', recursive=False):
                    doc.add_paragraph(li.get_text(), style='List Bullet')
            elif element.name == 'ol':
                for li in element.find_all('li', recursive=False):
                    doc.add_paragraph(li.get_text(), style='List Number')
            elif element.name == 'table':
                # 处理表格
                rows = element.find_all('tr')
                num_rows = len(rows)
                try:
                    num_cols = len(rows[0].find_all(['th', 'td']))

                    # 创建 Word 表格
                    table = doc.add_table(rows=num_rows, cols=num_cols)
                    table.style = 'Table Grid'  # 您可以根据需要更改表格样式

                    # 遍历表格的每一行
                    for i, row in enumerate(rows):
                        cells = row.find_all(['th', 'td'])
                        for j, cell in enumerate(cells):
                            # 将单元格文本添加到 Word 表格中
                            table.cell(i, j).text = cell.get_text(strip=True)
                except:
                    print(f"Unknown error")
        doc.save(word_path)

    def translate_markdown_folder(translating_files: list[NamedString],
                                  selected_model: Optional[str], selected_lora_model: Optional[str],
                                  selected_gpu: Optional[str], batch_size: int,
                                  original_language: Optional[str], target_language: Optional[str]):
        start_time = time.time()
        if not translating_files:
            return "No files uploaded", []

        folder_path = os.path.dirname(translating_files[0].name)
        processed_files = []

        # 创建保存翻译文件的文件夹
        processed_folder = os.path.join(folder_path, 'processed')
        os.makedirs(processed_folder, exist_ok=True)

        for input_file in translating_files:
            file_path = input_file.name
            file_name, file_ext = os.path.splitext(file_path)

            if file_ext.lower() == '.pptx':
                def extract_text_from_shape(shape, run_list, text_list):
                    """递归提取所有文本，包括文本框、表格和嵌套形状"""
                    if hasattr(shape, "text_frame") and shape.text_frame is not None:
                        # 处理普通文本框
                        for paragraph in shape.text_frame.paragraphs:
                            for run in paragraph.runs:
                                run_list.append(run)
                                text_list.append(run.text)
                    elif getattr(shape, "has_table", False):
                        # 仅当 shape 确实包含表格时进行处理
                        table = shape.table
                        for row in table.rows:
                            for cell in row.cells:
                                if cell.text_frame is not None:
                                    for paragraph in cell.text_frame.paragraphs:
                                        for run in paragraph.runs:
                                            run_list.append(run)
                                            text_list.append(run.text)
                    elif hasattr(shape, "shapes"):
                        # 处理嵌套的 grouped shapes
                        for sub_shape in shape.shapes:
                            extract_text_from_shape(sub_shape, run_list, text_list)

                prs = Presentation(file_path)
                run_list = []
                text_list = []

                for slide in prs.slides:
                    for shape in slide.shapes:
                        extract_text_from_shape(shape, run_list, text_list)  # 确保提取所有文本

                # 翻译文本
                translated_segments = translate(text_list, selected_model, selected_lora_model, selected_gpu,
                                                batch_size, original_language, [target_language])
                
                # 替换原始文本
                for run, translated in zip(run_list, translated_segments):
                    run.text = " " + translated[0]["generated_translation"]
                
                # 保存 PPTX
                output_file_path = os.path.join(processed_folder, os.path.basename(file_name + '.pptx'))
                prs.save(output_file_path)
                processed_files.append(output_file_path)
            else:
                # 识别并转换 Word 文件
                if file_ext.lower() == '.docx':
                    md_content = word_to_markdown(file_path)
                    file_is_word = True
                elif file_ext.lower() == '.md':
                    with open(file_path, 'r', encoding='utf-8') as f:
                        md_content = f.read()
                    file_is_word = False
                else:
                    continue  # 跳过非 Word 或 Markdown 文件

                # 拆分 Markdown 内容进行翻译
                text_segments = md_content.split('\n\n')
                translated_segments = translate(text_segments, selected_model, selected_lora_model, selected_gpu,
                                                batch_size, original_language, [target_language])

                print(translated_segments)
                # 合并翻译内容
                translated_content = '\n\n'.join(
                    [translated_segment[0]["generated_translation"] for translated_segment in translated_segments])

                # 根据文件类型保存为 Markdown 或 Word
                output_file_path = os.path.join(processed_folder,
                                                os.path.basename(file_name + ('.docx' if file_is_word else '.md')))

                if file_is_word:
                    markdown_to_word(translated_content, output_file_path)
                else:
                    with open(output_file_path, 'w', encoding='utf-8') as f:
                        f.write(translated_content)

                processed_files.append(output_file_path)

        # 将所有处理后的文件压缩成一个 zip 文件
        zip_filename = os.path.join(folder_path, "processed_files.zip")
        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            for file in processed_files:
                zipf.write(file, os.path.basename(file))
                print(f"File {file} added to zip.")

        end_time = time.time()
        print(f"Total process time: {int(end_time - start_time)}s")
        print(f"Processed files: {processed_files}")

        return f"Total process time: {int(end_time - start_time)}s", zip_filename

    def glossary_check(input_folder, start_row, end_row, original_column, reference_column, translated_column,
                       row_selection, remark_column) -> str:
        def contains_special_string(sentence):
            # 定义特殊字符串的正则表达式模式字典
            patterns = {
                "Content within <% ... %> should not be translated": r"<%.*?%>",  # Match <% ... %>
                "Special symbol %s should be contained": r"%s",  # Match %s
                "Special symbols {0}, {1}, {2}, etc., should not be translated": r"{\d+}",  # Match {0}, {1}, {2}, etc.
                "Special symbol %d should be contained": r"%d",  # Match %d
                "String {counts} should not be translated": r"{counts}",  # Match {counts}
                "String (value) should not be translated": r"\(value\)",  # Match (value)
                "String (Value) should not be translated": r"\(Value\)",  # Match (Value)
                "String (text) should not be translated": r"\(text\)",  # Match (text)
                "String (Text) should not be translated": r"\(Text\)",  # Match (Text)
                "String (message) should not be translated": r"\(message\)",  # Match (message)
                "String (Message) should not be translated": r"\(Message\)",  # Match (Message)
                "String (group) should not be translated": r"\(group\)",  # Match (group)
                "String (Group) should not be translated": r"\(Group\)",  # Match (Group)
                "Content within &{...}& should not be translated": r"&{.*?}&",  # Match &{...}&
                "String {} should be contained": r"{}",  # Match {}
                "Content within #...# should not be translated": r"#.*?#",  # Match #...#
                "Content within {{...}} should not be translated": r"{{.*?}}",  # Match {{...}}
                "Consecutive uppercase letters (AR, AP, SKU) should be contained": r"[A-Z]{2,}",
                # Match consecutive uppercase letters
                "CamelCase words (e.g., ServiceCode, LocStudio) should be contained": r"(?:[A-Z][a-z]+){2,}",
                # Match CamelCase words
                "Full links http:// should be contained": r"http://",  # Match full links containing "http://"
                "Full links https:// should be contained": r"https://",  # Match full links containing "https://"
                "Full file paths E:\, D:\, C:\ should be contained": r"[CDE]:\\",
                # Match file paths with "E:\", "D:\", "C:\"
                "Formula-like strings such as datediff(.*?,.*?,.*?) should not be translated": r"datediff\(.*?,.*?,.*?\)",
                # Match datediff
                "Strings like @BusinessFunction. ... @ should not be translated": r"@业务函数\..*?@",
                # Match @BusinessFunction. ... @
                "CamelCase words starting with a lowercase letter (e.g., serviceCode, locStudio) should not be translated": r"[a-z]+[a-z]*[A-Z][a-zA-Z]*",
                # Match camelCase words
                "String ${label} should not be translated": r"\$\{label\}",                       # 如："${label}"，字段名称
                "String [${enum}] should not be translated": r"\[\$\{enum\}\]",                   # 如："[${enum}]"，枚举字段
                "String ${max} should not be translated": r"\$\{max\}",                           # 最大值字段
                "String ${min} should not be translated": r"\$\{min\}",                           # 最小值字段
                "String ${len} should not be translated": r"\$\{len\}",                           # 长度字段
                "String ${pattern} should not be translated": r"\$\{pattern\}",                   # 正则表达式字段
                "String [{{fievent}}] should not be translated": r"\[\{\{fievent\}\}\]",
                "String [{{accBook}}] should not be translated": r"\[\{\{accBook\}\}\]",
            }

            reasons = []  # 用于存储匹配的条目
            matched_strings = []  # 用于存储被识别的字符串
            for reason, pattern in patterns.items():
                matches = re.findall(pattern, sentence)
                if matches:
                    reasons.append(reason)
                    matched_strings.extend(matches)
            return {
                "contains_special_string": bool(reasons),  # 如果 reasons 列表不为空，表示匹配
                "reason": reasons,  # 返回所有匹配条目
                "matched_strings": matched_strings  # 返回所有被识别的字符串
            }

        result = []
        excel_writer = ExcelFileWriter()
        folder_path = os.path.dirname(input_folder[0].name)
        processed_files = []

        # Create a new folder named 'processed' within the uploaded folder
        processed_folder = os.path.join(folder_path, 'processed')
        os.makedirs(processed_folder, exist_ok=True)
        for input_file in input_folder:
            file_path = input_file.name
            file_name, file_ext = os.path.splitext(file_path)
            if file_ext == '.xlsx':
                if row_selection == "所有行":
                    end_row = FileReaderFactory.count_rows(file_path)
                reader, fp = FileReaderFactory.create_reader(file_path)
                original_inputs = reader.extract_text(file_path, original_column, start_row, end_row)
                reference_inputs = reader.extract_text(file_path, reference_column, start_row, end_row)
                translated_inputs = reader.extract_text(file_path, translated_column, start_row, end_row)
                result.append(f"{file_name}:")
                outputs = []
                for index, (original_input, reference_input, translated_input) in enumerate(
                        zip(original_inputs, reference_inputs, translated_inputs)):
                    special_string = contains_special_string(original_input)
                    # print(outputs["matched_strings"])
                    if special_string["contains_special_string"]:
                        temp_miss_match = []
                        for reason, matched_string in zip(special_string["reason"], special_string["matched_strings"]):

                            if matched_string in translated_input:
                                continue
                            else:
                                if matched_string.lower() not in reference_input.lower():
                                    continue
                                else:
                                    temp_miss_match.append([matched_string, reason])
                        if temp_miss_match != []:
                            result.append(
                                f"\tROW : {start_row + index}, MISSED : {','.join([miss_match[0] for miss_match in temp_miss_match])}, REASON : {','.join([miss_match[1] for miss_match in temp_miss_match])}")
                            outputs.append(
                                f"MISSED : {','.join([miss_match[0] for miss_match in temp_miss_match])}, REASON : {','.join([miss_match[1] for miss_match in temp_miss_match])}")
                        else:
                            if any(s.isupper() for s in special_string["matched_strings"]):
                                outputs.append("SPECIAL VALUE, INCLUDE UPPERCASE LETTER")
                            else:
                                outputs.append("SPECIAL VALUE")
                    else:
                        outputs.append("")
                    if len(tokenizer.encode(original_input)) > 40:
                        outputs[-1] = outputs[-1] + ", Content length exceeds 30 tokens"
                output_file = excel_writer.write_list(file_path, outputs, remark_column, start_row, end_row)
                processed_file_path = os.path.join(processed_folder, os.path.basename(output_file))
                shutil.move(output_file, processed_file_path)
                processed_files.append(processed_file_path)

        # Create a zip file 
        zip_filename = os.path.join(folder_path, "processed_files.zip")
        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            for file in processed_files:
                zipf.write(file, os.path.basename(file))
            print(f"{file_name} 已检测完成")
        return "\n".join(result), zip_filename

    with gr.Blocks(title="yonyou translator") as interface:
        gr.Button("Logout", link="/logout")
        with gr.Tabs():
            with gr.TabItem("Excel Translator"):
                with gr.Row():
                    with gr.Column():
                        input_file = gr.File()
                        with gr.Row():
                            start_row = gr.Number(value=2, label="起始行")
                            end_row = gr.Number(value=100001, label="终止行")
                            target_column = gr.Textbox(value="J", label="目标列")
                            start_column = gr.Textbox(value="K", label="结果写入列")
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
                selected_model.change(update_choices, inputs=[selected_model],
                                      outputs=[original_language, target_languages, selected_lora_model,
                                               model_explanation_textbox])
                translate_button.click(translate_excel,
                                       inputs=[input_file, start_row, end_row, start_column, target_column,
                                               selected_model, selected_lora_model, selected_gpu, batch_size,
                                               original_language, target_languages], outputs=[output_text, output_file])
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
                            target_languages = gr.Dropdown(choices=available_languages, label="目标语言",
                                                           multiselect=True)
                        translate_button = gr.Button("Translate")
                    with gr.Column():
                        model_explanation_textbox = gr.Textbox(label="模型介绍", lines=5)
                        output_text = gr.Textbox(label="输出文本", lines=5)
                selected_model.change(update_choices, inputs=[selected_model],
                                      outputs=[original_language, target_languages, selected_lora_model,
                                               model_explanation_textbox])
                translate_button.click(translate, inputs=[input_text, selected_model, selected_lora_model, selected_gpu,
                                                          batch_size, original_language, target_languages],
                                       outputs=output_text)
            # folder translator
            with gr.TabItem("Folder Excel Translator"):
                with gr.Row():
                    with gr.Column():
                        input_folder = gr.File(file_count="directory")
                        with gr.Row():
                            start_row = gr.Number(value=yaml_data["excel_config"]["default_start_row"], label="起始行")
                        with gr.Row():
                            row_selection = gr.Radio(choices=["特定行", "所有行"], label="行选择", value="特定行")
                            end_row = gr.Number(value=yaml_data["excel_config"]["default_end_row"], label="终止行",
                                                visible=True)
                        row_selection.change(update_row_selection, inputs=row_selection, outputs=end_row)

                        with gr.Row():
                            target_column = gr.Textbox(value=yaml_data["excel_config"]["default_target_column"],
                                                       label="目标列")
                            start_column = gr.Textbox(value=yaml_data["excel_config"]["default_start_column"],
                                                      label="结果写入列")
                        with gr.Row():
                            selected_model = gr.Dropdown(choices=(available_models.keys()), label="选择基模型")
                            selected_lora_model = gr.Dropdown(choices=[], label="选择Lora模型")
                            selected_gpu = gr.Dropdown(choices=available_gpus, label="选择GPU", value=available_gpus[0])
                            batch_size = gr.Number(value=1, label="批处理大小", visible=True)
                        with gr.Row():
                            original_language = gr.Dropdown(choices=available_languages, label="原始语言")
                            target_languages = gr.Dropdown(choices=available_languages, label="目标语言",
                                                           multiselect=True)
                        translate_button = gr.Button("Translate")
                    with gr.Column():
                        model_explanation_textbox = gr.Textbox(label="模型介绍", lines=5)
                        output_text = gr.Textbox(label="输出文本", lines=5)
                        output_folder = gr.File(label="翻译文件夹下载")
                selected_model.change(update_choices, inputs=[selected_model],
                                      outputs=[original_language, target_languages, selected_lora_model,
                                               model_explanation_textbox])
                translate_button.click(translate_excel_folder,
                                       inputs=[input_folder, start_row, end_row, start_column, target_column, 
                                               selected_model, selected_lora_model, selected_gpu, batch_size,
                                               original_language, target_languages, row_selection],
                                       outputs=[output_text, output_folder])
            with gr.TabItem("Folder Markdown & Docx Translator"):
                with gr.Row():
                    with gr.Column():
                        input_folder = gr.File(file_count="directory", label="选择包含Markdown或Docx文件夹")
                        row_selection.change(update_row_selection, inputs=row_selection, outputs=end_row)

                        with gr.Row():
                            selected_model = gr.Dropdown(choices=available_models.keys(), label="选择基模型")
                            selected_lora_model = gr.Dropdown(choices=[], label="选择Lora模型")
                            selected_gpu = gr.Dropdown(choices=available_gpus, label="选择GPU", value=available_gpus[0])
                            batch_size = gr.Number(value=1, label="批处理大小", visible=True)
                        with gr.Row():
                            original_language = gr.Dropdown(choices=available_languages, label="原始语言")
                            target_language = gr.Dropdown(choices=available_languages, label="目标语言")
                        translate_button = gr.Button("Translate")

                    with gr.Column():
                        model_explanation_textbox = gr.Textbox(label="模型介绍", lines=5)
                        output_text = gr.Textbox(label="输出文本", lines=5)
                        output_folder = gr.File(label="翻译文件夹下载")

                # Link actions to the dropdown and button
                selected_model.change(update_choices,
                                      inputs=[selected_model],
                                      outputs=[original_language, target_language, selected_lora_model,
                                               model_explanation_textbox])
                translate_button.click(translate_markdown_folder,
                                       inputs=[input_folder, selected_model, selected_lora_model, selected_gpu,
                                               batch_size, original_language, target_language],
                                       outputs=[output_text, output_folder])
            with gr.TabItem("术语表校验"):
                with gr.Row():
                    with gr.Column():
                        input_folder = gr.File(file_count="directory")
                        with gr.Row():
                            row_selection = gr.Radio(choices=["特定行", "所有行"], label="行选择", value="特定行")
                            start_row = gr.Number(value=yaml_data["excel_config"]["default_start_row"], label="起始行")
                            end_row = gr.Number(value=yaml_data["excel_config"]["default_end_row"], label="终止行",
                                                visible=True)
                        row_selection.change(update_row_selection, inputs=row_selection, outputs=end_row)
                        with gr.Row():
                            original_column = gr.Textbox("J", label="原文列")
                            reference_column = gr.Textbox("G", label="参考列")
                            translated_column = gr.Textbox("H", label="已翻译列")
                        with gr.Row():
                            remark_column = gr.Textbox("I", label="备注")
                        translate_button = gr.Button("开始检测")

                    with gr.Column():
                        output_text = gr.Textbox(label="输出文本", lines=20, show_copy_button=True)
                        output_folder = gr.File(label="特殊词条标注文件下载")

                translate_button.click(glossary_check,
                                       inputs=[input_folder, start_row, end_row, original_column, reference_column,
                                               translated_column, row_selection, remark_column],
                                       outputs=[output_text, output_folder])

    return interface


main_ui = webui()

if __name__ == "__main__":
    main_ui.launch(share=True, server_port=8080)
