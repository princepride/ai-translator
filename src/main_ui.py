





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
    # available_languages = [] # 注释掉或者移除这行，因为语言选项由 update_choices 动态生成

    default_model_name = "chatgpt-4o-mini" # 定义默认模型名称
    default_original_language = "Chinese"  # 定义默认原始语言
    default_target_language_single = "English" # 定义默认目标语言 (单选)
    default_target_language_multi = ["English"] # 定义默认目标语言 (多选)


    def update_choices(selected_model):
        model_path = available_models.get(selected_model) # 使用 .get() 更安全
        original_language_choices = []
        target_language_choices = []
        lora_list = ['']
        model_explanation = "Model path not found or README.md missing."

        if model_path:
            support_language_path = os.path.join(model_path, 'support_language.json')
            readme_path = os.path.join(model_path, 'README.md')

            if os.path.isfile(readme_path):
                try:
                    with open(readme_path, 'r', encoding='utf-8') as file:
                        model_explanation = file.read()
                except Exception as e:
                    print(f"Error reading README.md: {e}")
                    model_explanation = f"Error reading README.md: {e}"

            try:
                with open(support_language_path, 'r') as file:
                    support_languages = json.load(file)
                    original_language_choices = support_languages.get("original_language", [])
                    target_language_choices = support_languages.get("target_language", [])
            except Exception as e:
                print(f"Error reading support_language.json: {e}")
                # Keep choices empty if file read fails

            try:
                lora_list = [''] + [f for f in os.listdir(model_path) if
                                    os.path.isdir(os.path.join(model_path, f)) and not f.startswith('.') and not f.startswith(
                                        '_')]
            except Exception as e:
                print(f"Error listing lora models in {model_path}: {e}")
                lora_list = [''] # Reset to default if error

        # --- 重要: 返回更新后的组件，同时确保默认值在 choices 中 ---
        # 如果默认值不在动态加载的choices里，Gradio 可能无法正确显示默认值
        # 这里假设 'Chinese' 和 'English' 通常会存在于加载的语言列表中
        # 如果模型不支持这些语言，默认值可能不会被选中
        return (gr.Dropdown(choices=original_language_choices, value=default_original_language if default_original_language in original_language_choices else None),
                gr.Dropdown(choices=target_language_choices, value=default_target_language_multi if default_target_language_single in target_language_choices else None, multiselect=True), # 处理多选的情况
                gr.Dropdown(choices=lora_list), # Lora 模型通常没有默认值，除了空字符串
                model_explanation)

    # --- translate_excel, translate, translate_excel_folder, word_to_markdown, markdown_to_word, translate_markdown_folder, glossary_check 函数保持不变 ---
    # (省略这些函数的代码以保持简洁)
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
        model_path = available_models.get(selected_model)
        if not model_path:
             print(f"Model '{selected_model}' not found in available models.")
             return [] # Return empty list or handle error appropriately

        model_file_path = os.path.join(model_path, 'model.py')
        # 检查文件是否存在
        if not os.path.exists(model_file_path):
            print(f"No model.py found in {model_path}")
            return [] # Return empty list or handle error appropriately
        spec = importlib.util.spec_from_file_location("model", model_file_path)
        if spec is None or spec.loader is None:
            print(f"Could not load spec for model.py in {model_path}")
            return []
        model_module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(model_module)
        except Exception as e:
            print(f"Error executing module {model_file_path}: {e}")
            return []
        outputs = []
        if hasattr(model_module, 'Model'):
            try:
                # Pass the base directory, not the model.py path itself
                model = model_module.Model(model_path, selected_lora_model, selected_gpu)
                if hasattr(model, 'generate'):
                    outputs = model.generate(inputs, original_language, target_languages, batch_size)
                else:
                    print("Model class does not have a 'generate' method.")
            except Exception as e:
                print(f"Error instantiating or running model from {model_path}: {e}")
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
            # This might be tricky with Gradio File objects, ensure .name is updated if needed
            original_file_obj_name = input_file.name # Store original name if needed
            if file_path != updated_file_path:
                 # Be cautious modifying Gradio object properties directly if it causes issues
                 # It might be better to work with updated_file_path directly
                 # input_file.name = updated_file_path # Potentially risky
                 file_path_to_process = updated_file_path
                 # Create a NamedString or handle appropriately if translate_excel expects Gradio object
                 temp_file_obj = NamedString(name=updated_file_path, data="", is_file=True) # Example adjustment
            else:
                 file_path_to_process = file_path
                 temp_file_obj = input_file # Use original object

            current_end_row = end_row
            if row_selection == "所有行":
                try:
                   current_end_row = FileReaderFactory.count_rows(file_path_to_process)
                except Exception as e:
                   print(f"Could not count rows for {file_path_to_process}: {e}. Skipping file or using default end_row.")
                   continue # Or handle error differently

            try:
                # Pass the potentially modified file object/path
                process_time, output_file = translate_excel(temp_file_obj, start_row, current_end_row, start_column, target_column,
                                                            selected_model, selected_lora_model, selected_gpu, batch_size,
                                                            original_language, target_languages)

                # output_file is likely a path string returned by excel_writer
                if output_file and os.path.exists(output_file):
                     processed_file_path = os.path.join(processed_folder, os.path.basename(output_file))
                     shutil.move(output_file, processed_file_path)
                     processed_files.append(processed_file_path)
                else:
                     print(f"Translation failed or output file path invalid for {original_file_obj_name}")

            except Exception as e:
                print(f"Error processing file {original_file_obj_name}: {e}")
                continue # Skip to next file on error


        # Create a zip file
        zip_filename = os.path.join(folder_path, "processed_files.zip")
        if not processed_files:
             print("No files were processed successfully.")
             return "No files processed successfully.", None # Return None for zip file

        try:
            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                for file in processed_files:
                    if os.path.exists(file):
                         zipf.write(file, os.path.basename(file))
                         print(f"File {file} added to zip.")
                    else:
                         print(f"Warning: Processed file {file} not found for zipping.")
        except Exception as e:
            print(f"Error creating zip file {zip_filename}: {e}")
            return f"Error creating zip file: {e}", None


        end_time = time.time()
        print(f"Total process time: {int(end_time - start_time)}s")
        print(f"Processed files added to zip: {processed_files}")
        return f"Total process time: {int(end_time - start_time)}s. {len(processed_files)} file(s) processed.", zip_filename

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
            if not hasattr(parent, 'element') or not hasattr(parent.element, 'body'):
                 print("Warning: Could not access parent element body.")
                 return # Or raise an error
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
                try:
                    rels_elm = parse_xml(rels_item_xml)
                    for rel_elm in rels_elm.Relationship_lst:
                        # Check for target_ref attribute existence before accessing
                        if hasattr(rel_elm, 'target_ref') and rel_elm.target_ref not in ('../NULL', 'NULL', None):
                            srels._srels.append(_SerializedRelationship(baseURI, rel_elm))
                except Exception as e:
                    print(f"Error parsing relationships XML: {e}") # Log error
            return srels

        # Monkey patch the method carefully
        _SerializedRelationships.load_from_xml = load_from_xml_v2
        try:
            doc = Document(docx_path)
        except Exception as e:
            print(f"Error opening document {docx_path}: {e}")
            return "" # Return empty string on error

        md_content = ""

        # 用于图片计数，生成唯一的图片名称
        image_counter = 1
        image_paths_generated = [] # Track generated image paths for cleanup or verification

        for block in iter_block_items(doc):
            if isinstance(block, Paragraph):
                para = block
                run_texts = [] # Collect text from runs first
                # 处理图片
                for run in para.runs:
                    # 检查 run 中是否有图片
                    drawing_elements = run.element.findall(
                        './/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing')
                    image_found_in_run = False
                    for drawing in drawing_elements:
                        # 提取图片
                        blip_elements = drawing.findall(
                            './/{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
                        for blip in blip_elements:
                            rEmbed = blip.get(
                                '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                            if rEmbed and hasattr(doc.part, 'related_parts') and rEmbed in doc.part.related_parts:
                                try:
                                    image_part = doc.part.related_parts[rEmbed]
                                    image_bytes = image_part.blob
                                    # Try to determine a better extension if possible, default to png
                                    ext = os.path.splitext(image_part.partname)[-1] or ".png"
                                    if ext.lower() not in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff']:
                                         ext = ".png" # Default extension
                                    image_name = f"image_{image_counter}{ext}"
                                    image_path = os.path.join(output_dir, image_name)
                                    with open(image_path, 'wb') as f:
                                        f.write(image_bytes)
                                    # Use relative path for markdown if output_dir is relative
                                    md_image_path = os.path.join(os.path.basename(output_dir), image_name) # More robust relative path
                                    md_content += f"![{image_name}]({md_image_path})\n\n"
                                    image_paths_generated.append(image_path)
                                    image_counter += 1
                                    image_found_in_run = True
                                except Exception as e:
                                    print(f"Error processing image resource {rEmbed}: {e}")
                            else:
                                print(f"Warning: Missing or invalid image resource for {rEmbed}")
                    # Append run text only if no image was processed from this run
                    # to avoid duplicate text if image is inline with text
                    if not image_found_in_run:
                         run_texts.append(run.text)

                # Process collected paragraph text after handling images
                para_text = "".join(run_texts)
                if para.style and para.style.name and para.style.name.startswith('Heading'):
                    try:
                         level = int(para.style.name.split()[-1]) # Safer split
                         # Add heading text only if it wasn't part of a run handled above
                         if para.text: # Check if paragraph itself has text (might be empty if only image)
                              md_content += f"{'#' * level} {para.text.strip()}\n\n"
                    except (ValueError, IndexError):
                         # Fallback for non-standard heading names
                         if para.text.strip():
                              md_content += f"### {para.text.strip()}\n\n" # Default to H3
                elif para_text.strip(): # Use collected text
                    md_content += f"{para_text.strip()}\n\n"

            elif isinstance(block, Table):
                table = block
                md_content += "\n"
                # 获取表格的所有行
                rows = table.rows
                if len(rows) > 0:
                    # 生成表头
                    header_cells = rows[0].cells
                    # Ensure cell.text is not None before strip()
                    header = "| " + " | ".join((cell.text or "").strip().replace('\n', ' ') for cell in header_cells) + " |\n"
                    md_content += header
                    # 添加分隔行
                    md_content += "| " + " | ".join(['---'] * len(header_cells)) + " |\n"
                    # 添加表格内容
                    for row in rows[1:]:
                        row_cells = row.cells
                        row_text = "| " + " | ".join(
                            (cell.text or "").strip().replace('\n', ' ') for cell in row_cells) + " |\n"
                        md_content += row_text
                md_content += "\n"

        print(f"Generated images: {image_paths_generated}") # Optional: log generated images
        return md_content

    def markdown_to_word(md_content, word_path, image_base_dir="images"):
        # 将 Markdown 内容转换为 HTML，并启用表格扩展
        try:
            html = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
        except Exception as e:
            print(f"Error converting Markdown to HTML: {e}")
            return # Or raise error

        try:
            soup = BeautifulSoup(html, 'html.parser')
        except Exception as e:
            print(f"Error parsing generated HTML: {e}")
            return # Or raise error

        doc = Document()
        # Add default styles if needed, e.g., for code blocks
        # from docx.shared import Pt
        # style = doc.styles['Normal']
        # font = style.font
        # font.name = 'Calibri' # Example font
        # font.size = Pt(11)

        for element in soup.contents:
             if not hasattr(element, 'name'): # Handle NavigableString (text nodes)
                  text = str(element).strip()
                  if text:
                       doc.add_paragraph(text)
                  continue

             if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                  try:
                       level = int(element.name[1])
                       doc.add_heading(element.get_text(strip=True), level=level)
                  except (ValueError, IndexError):
                       doc.add_heading(element.get_text(strip=True), level=3) # Fallback
             elif element.name == 'p':
                 # Process paragraph content, including inline elements like <img>
                 current_paragraph = doc.add_paragraph()
                 for content_item in element.contents:
                     if hasattr(content_item, 'name') and content_item.name == 'img':
                         img_src = content_item.get('src')
                         alt_text = content_item.get('alt', '')
                         # Construct full image path relative to the script or a known base
                         # Assume image_base_dir is relative to where the script runs or word_path is saved
                         img_path = os.path.abspath(img_src) # Try absolute first if src is already somewhat resolved
                         if not os.path.exists(img_path):
                             # If not found, try relative to image_base_dir
                             img_path = os.path.join(image_base_dir, img_src)

                         if os.path.exists(img_path):
                             try:
                                 # Add picture inline if possible, or as separate paragraph item
                                 # Adding run first might allow inline placement, but complex.
                                 # Simpler: add picture, which often creates its own paragraph implicitly or use add_run().add_picture().
                                 # Let's add as its own element for simplicity now.
                                 doc.add_picture(img_path, width=Inches(4)) # Adjust width as needed
                                 # If alt text exists, maybe add as a caption paragraph below
                                 if alt_text:
                                     # Adding a new paragraph for caption
                                     caption_paragraph = doc.add_paragraph(alt_text)
                                     caption_paragraph.alignment = 1 # WD_ALIGN_PARAGRAPH.CENTER
                                     # Reset current_paragraph for text after image
                                     current_paragraph = doc.add_paragraph()
                             except Exception as e:
                                 print(f"Warning: Could not add picture {img_path}. Error: {e}")
                                 current_paragraph.add_run(f"[Image: {alt_text or img_src}]") # Placeholder text
                         else:
                             print(f"Warning: Could not find image file {img_path} (tried from {img_src})")
                             current_paragraph.add_run(f"[Image not found: {alt_text or img_src}]") # Placeholder text
                     elif hasattr(content_item, 'name') and content_item.name in ['strong', 'em', 'b', 'i', 'code']:
                          # Handle basic inline formatting
                          run = current_paragraph.add_run(content_item.get_text())
                          if content_item.name in ['strong', 'b']:
                               run.bold = True
                          if content_item.name in ['em', 'i']:
                               run.italic = True
                          # if content_item.name == 'code':
                          #     run.font.name = 'Courier New' # Example for code
                     elif hasattr(content_item, 'name') and content_item.name == 'br':
                          current_paragraph.add_run().add_break()
                     else:
                          # Append text nodes or other unhandled inline elements as plain text
                          text = content_item.get_text(strip=False) if hasattr(content_item, 'get_text') else str(content_item)
                          current_paragraph.add_run(text)
                 # Remove paragraph if it only contains whitespace after processing
                 if not current_paragraph.text.strip() and not any(isinstance(inline, docx.shape.InlineShape) for inline in current_paragraph.runs):
                      # This check might be complex; simpler to just leave potentially empty paras
                      pass

             elif element.name == 'ul':
                 for li in element.find_all('li', recursive=False):
                     doc.add_paragraph(li.get_text(strip=True), style='List Bullet')
             elif element.name == 'ol':
                 for li in element.find_all('li', recursive=False):
                     doc.add_paragraph(li.get_text(strip=True), style='List Number')
             elif element.name == 'pre' and element.find('code'):
                  # Handle code blocks
                  code_text = element.find('code').get_text()
                  p = doc.add_paragraph(style='BodyText') # Or a custom code style
                  run = p.add_run(code_text)
                  # run.font.name = 'Courier New' # Example code font
                  # Add shading or borders if needed via paragraph formatting
             elif element.name == 'table':
                 # Handle tables
                 rows = element.find_all('tr')
                 if not rows: continue # Skip empty tables

                 num_cols = 0
                 first_row_cells = rows[0].find_all(['th', 'td'])
                 if first_row_cells:
                      num_cols = len(first_row_cells)
                 if num_cols == 0: continue # Skip tables with no columns in first row

                 num_rows = len(rows)

                 try:
                     # Create Word table
                     table = doc.add_table(rows=num_rows, cols=num_cols)
                     table.style = 'Table Grid'  # Apply a style

                     # Populate table
                     for i, row in enumerate(rows):
                         cells = row.find_all(['th', 'td'])
                         # Ensure we don't try to access cells beyond num_cols
                         for j, cell in enumerate(cells[:num_cols]):
                             # Handle potential cell spanning later if needed (more complex)
                             if i < len(table.rows) and j < len(table.columns):
                                  table.cell(i, j).text = cell.get_text(strip=True)
                 except Exception as e:
                     print(f"Error creating or populating table in Word: {e}")
                     doc.add_paragraph(f"[Error converting table: {e}]") # Placeholder for table

        try:
            doc.save(word_path)
        except Exception as e:
            print(f"Error saving Word document to {word_path}: {e}")


    def translate_markdown_folder(translating_files: list[NamedString],
                                  selected_model: Optional[str], selected_lora_model: Optional[str],
                                  selected_gpu: Optional[str], batch_size: int,
                                  original_language: Optional[str], target_language: Optional[str]):
        start_time = time.time()
        if not translating_files:
            return "No files uploaded", None # Return None for file path

        folder_path = os.path.dirname(translating_files[0].name) # Base path from first file
        processed_files = []
        temp_image_dir = os.path.join(folder_path, "temp_images") # Temp dir for images from docx

        # 创建保存翻译文件的文件夹 和 临时图片文件夹
        processed_folder = os.path.join(folder_path, 'processed')
        os.makedirs(processed_folder, exist_ok=True)
        os.makedirs(temp_image_dir, exist_ok=True)

        for input_file in translating_files:
            file_path = input_file.name
            file_name, file_ext = os.path.splitext(os.path.basename(file_path)) # Use basename

            output_file_path = None # Initialize output path

            try:
                if file_ext.lower() == '.pptx':
                    # --- PPTX Processing ---
                    def extract_text_from_shape(shape, run_map):
                        """递归提取，并将 run 映射到其文本"""
                        if hasattr(shape, "text_frame") and shape.text_frame is not None:
                            for paragraph in shape.text_frame.paragraphs:
                                for run in paragraph.runs:
                                    if run.text and run.text.strip(): # Only include runs with actual text
                                         run_map[id(run)] = run # Use id as unique key for the run object
                        elif getattr(shape, "has_table", False):
                            table = shape.table
                            for row in table.rows:
                                for cell in row.cells:
                                    if cell.text_frame is not None:
                                        for paragraph in cell.text_frame.paragraphs:
                                            for run in paragraph.runs:
                                                 if run.text and run.text.strip():
                                                      run_map[id(run)] = run
                        elif hasattr(shape, "shapes"): # Group shape
                            for sub_shape in shape.shapes:
                                extract_text_from_shape(sub_shape, run_map)

                    prs = Presentation(file_path)
                    run_map = {} # Maps run id to run object

                    for slide in prs.slides:
                        for shape in slide.shapes:
                            extract_text_from_shape(shape, run_map)

                    original_texts = [run.text for run in run_map.values()]

                    if not original_texts:
                         print(f"No text found in {file_path}. Skipping.")
                         continue # Skip if no text

                    # Translate collected texts
                    # Ensure target_language is a list for the translate function if it expects one
                    target_lang_list = [target_language] if isinstance(target_language, str) else target_language
                    translated_results = translate(original_texts, selected_model, selected_lora_model, selected_gpu,
                                                 batch_size, original_language, target_lang_list)

                    # Check translation results format (assuming list of lists with dicts)
                    if not translated_results or not isinstance(translated_results, list) or not all(isinstance(item, list) and item for item in translated_results):
                         print(f"Translation failed or returned unexpected format for {file_path}. Skipping.")
                         continue # Skip if translation failed

                    # Create mapping from original text index to translated text
                    translated_texts_map = {}
                    if len(translated_results) == len(original_texts):
                         for i, result_list in enumerate(translated_results):
                             if result_list and isinstance(result_list[0], dict) and "generated_translation" in result_list[0]:
                                  translated_texts_map[i] = result_list[0]["generated_translation"]
                             else:
                                  print(f"Warning: Translation result format incorrect for segment {i} in {file_path}. Using original.")
                                  translated_texts_map[i] = original_texts[i] # Fallback to original
                    else:
                         print(f"Warning: Mismatch between original text count ({len(original_texts)}) and translation results ({len(translated_results)}) for {file_path}. Skipping update.")
                         continue # Skip updating this file

                    # Update runs with translated text using the run_map and index map
                    run_list = list(run_map.values()) # Get runs in the order texts were extracted
                    for i, run in enumerate(run_list):
                         if i in translated_texts_map:
                             # Preserve original formatting as much as possible by only changing text
                             run.text = translated_texts_map[i]
                         else:
                             # Should not happen if counts match, but as a safeguard
                             print(f"Warning: No translation found for run index {i} in {file_path}.")


                    # Save the modified presentation
                    output_file_path = os.path.join(processed_folder, os.path.basename(file_name + '_translated.pptx'))
                    prs.save(output_file_path)

                elif file_ext.lower() in ['.docx', '.md']:
                    # --- DOCX / MD Processing ---
                    md_content = ""
                    file_is_word = False
                    if file_ext.lower() == '.docx':
                        # Use the temporary image directory for extraction
                        md_content = word_to_markdown(file_path, output_dir=temp_image_dir)
                        if not md_content: # Handle error from word_to_markdown
                             print(f"Failed to convert {file_path} to Markdown. Skipping.")
                             continue
                        file_is_word = True
                    elif file_ext.lower() == '.md':
                        with open(file_path, 'r', encoding='utf-8') as f:
                            md_content = f.read()
                        file_is_word = False

                    # Split Markdown content for translation (improved splitting)
                    # Split by double newline, but keep track of image/table blocks
                    text_segments = []
                    current_segment = ""
                    is_complex_block = False # Flag for images/tables that shouldn't be split mid-block
                    for line in md_content.splitlines():
                         stripped_line = line.strip()
                         # Check for start/end of complex blocks (basic check)
                         if stripped_line.startswith("![") or stripped_line.startswith("|") or stripped_line.startswith("---"):
                              is_complex_block = True
                         elif not stripped_line and is_complex_block: # End of complex block on empty line
                              is_complex_block = False

                         if not stripped_line and not is_complex_block and current_segment:
                              # Split on empty line if not inside a table/image block
                              text_segments.append(current_segment.strip())
                              current_segment = ""
                         else:
                              current_segment += line + "\n"

                    if current_segment.strip(): # Add the last segment
                         text_segments.append(current_segment.strip())

                    # Filter out empty segments before translation
                    non_empty_segments = [seg for seg in text_segments if seg]

                    if not non_empty_segments:
                        print(f"No text segments found to translate in {file_path}. Skipping.")
                        translated_content = md_content # Keep original if no text to translate
                    else:
                        # Translate non-empty segments
                        target_lang_list = [target_language] if isinstance(target_language, str) else target_language
                        translated_results = translate(non_empty_segments, selected_model, selected_lora_model, selected_gpu,
                                                     batch_size, original_language, target_lang_list)

                        # Check and merge results
                        if not translated_results or len(translated_results) != len(non_empty_segments):
                             print(f"Translation failed or returned incorrect number of segments for {file_path}. Skipping update.")
                             translated_content = md_content # Keep original on error
                        else:
                             # Map translated results back (assuming order is preserved)
                             translated_map = {}
                             all_translations_valid = True
                             for i, result_list in enumerate(translated_results):
                                  if result_list and isinstance(result_list[0], dict) and "generated_translation" in result_list[0]:
                                       translated_map[i] = result_list[0]["generated_translation"]
                                  else:
                                       print(f"Warning: Translation result format incorrect for segment {i} in {file_path}. Using original.")
                                       translated_map[i] = non_empty_segments[i] # Fallback to original
                                       all_translations_valid = False


                             # Reconstruct content using original structure and translated text
                             final_segments = []
                             translated_idx = 0
                             current_rebuilt_segment = ""
                             is_complex_block_rebuild = False
                             for line in md_content.splitlines():
                                 stripped_line = line.strip()
                                 if stripped_line.startswith("![") or stripped_line.startswith("|") or stripped_line.startswith("---"):
                                      is_complex_block_rebuild = True
                                 elif not stripped_line and is_complex_block_rebuild:
                                      is_complex_block_rebuild = False

                                 # Append line to current rebuilt segment
                                 current_rebuilt_segment += line + "\n"

                                 # Check if this line ends a translatable block
                                 # This logic needs refinement - matching original segments is tricky
                                 # Simplified: assume translation applies to reconstructed segments roughly matching originals
                                 if not stripped_line and not is_complex_block_rebuild and current_rebuilt_segment.strip():
                                     original_segment_match = current_rebuilt_segment.strip()
                                     # Find which original non-empty segment this corresponds to
                                     # This matching is fragile. A better approach might involve markers.
                                     # For now, use the simple index mapping if lengths match.
                                     if translated_idx < len(non_empty_segments) and all_translations_valid:
                                         final_segments.append(translated_map.get(translated_idx, original_segment_match))
                                         translated_idx += 1
                                     else: # Fallback if mismatch or error
                                          final_segments.append(original_segment_match)

                                     # Add the double newline separator, then reset
                                     final_segments.append("") # Represent the blank line
                                     current_rebuilt_segment = ""


                             # Add the last segment if any
                             last_original_segment = current_rebuilt_segment.strip()
                             if last_original_segment:
                                  if translated_idx < len(non_empty_segments) and all_translations_valid:
                                       final_segments.append(translated_map.get(translated_idx, last_original_segment))
                                  else:
                                       final_segments.append(last_original_segment)


                             # Join with single newlines (as splitlines removed them) and handle double newlines
                             translated_content = "\n".join(final_segments)
                             # Post-process to restore double newlines where appropriate
                             translated_content = re.sub(r'\n\n+', '\n\n', translated_content).strip()


                    # Save based on original type
                    output_filename_base = os.path.basename(file_name + '_translated')
                    if file_is_word:
                        output_file_path = os.path.join(processed_folder, output_filename_base + '.docx')
                        # Pass the temp image dir base for markdown_to_word to find images
                        markdown_to_word(translated_content, output_file_path, image_base_dir=temp_image_dir)
                    else:
                        output_file_path = os.path.join(processed_folder, output_filename_base + '.md')
                        with open(output_file_path, 'w', encoding='utf-8') as f:
                            f.write(translated_content)
                else:
                    print(f"Skipping unsupported file type: {file_path}")
                    continue # Skip unsupported files

                if output_file_path and os.path.exists(output_file_path):
                    processed_files.append(output_file_path)
                else:
                    print(f"Output file was not generated or found for {file_path}")

            except Exception as e:
                 print(f"Error processing file {file_path}: {e}")
                 # Optionally add the original file to the zip on error, or log failure
                 continue # Continue with the next file

        # --- Zipping ---
        zip_filename = os.path.join(folder_path, "processed_files.zip")
        if not processed_files:
             print("No files were processed successfully.")
             # Clean up temp image dir if empty or only contains failed attempts
             try:
                 if os.path.exists(temp_image_dir) and not os.listdir(temp_image_dir):
                      shutil.rmtree(temp_image_dir)
             except OSError as e:
                 print(f"Error removing temp image directory {temp_image_dir}: {e}")
             return "No files processed successfully.", None

        try:
            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                for file in processed_files:
                    if os.path.exists(file):
                        zipf.write(file, os.path.basename(file))
                        print(f"File {os.path.basename(file)} added to zip.")
                    else:
                        print(f"Warning: Processed file {file} not found for zipping.")
        except Exception as e:
            print(f"Error creating zip file {zip_filename}: {e}")
            # Clean up temp image dir even if zipping fails
            try:
                if os.path.exists(temp_image_dir):
                     shutil.rmtree(temp_image_dir)
            except OSError as e_rm:
                 print(f"Error removing temp image directory {temp_image_dir}: {e_rm}")
            return f"Error creating zip file: {e}", None

        # Clean up temporary image directory after successful processing and zipping
        try:
             if os.path.exists(temp_image_dir):
                  shutil.rmtree(temp_image_dir)
                  print(f"Temporary image directory {temp_image_dir} removed.")
        except OSError as e:
             print(f"Error removing temporary image directory {temp_image_dir}: {e}")


        end_time = time.time()
        duration = int(end_time - start_time)
        print(f"Total process time: {duration}s")
        print(f"Processed files added to zip: {[os.path.basename(f) for f in processed_files]}")

        return f"Total process time: {duration}s. {len(processed_files)} file(s) processed.", zip_filename

    def glossary_check(input_folder, start_row, end_row, original_column, reference_column, translated_column,
                       row_selection, remark_column) -> tuple[str, Optional[str]]: # Return tuple[status, filepath]
        # ... (glossary_check implementation remains the same)
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
                "Consecutive uppercase letters (AR, AP, SKU) should be contained": r"\b[A-Z]{2,}\b", # Use \b for word boundaries
                "CamelCase words (e.g., ServiceCode, LocStudio) should be contained": r"\b(?:[A-Z][a-z]+){2,}\b", # Use \b
                "Full links http:// should be contained": r"http://",  # Match full links containing "http://"
                "Full links https:// should be contained": r"https://",  # Match full links containing "https://"
                "Full file paths E:\\, D:\\, C:\\ should be contained": r"\b[CDE]:\\", # Use \b
                "Formula-like strings such as datediff(.*?,.*?,.*?) should not be translated": r"datediff\(.*?,.*?,.*?\)",
                "Strings like @BusinessFunction. ... @ should not be translated": r"@业务函数\..*?@",
                "CamelCase words starting with a lowercase letter (e.g., serviceCode, locStudio) should not be translated": r"\b[a-z]+[A-Z][a-zA-Z]*\b", # Use \b
                "String ${label} should not be translated": r"\$\{label\}",
                "String [${enum}] should not be translated": r"\[\$\{enum\}\]",
                "String ${max} should not be translated": r"\$\{max\}",
                "String ${min} should not be translated": r"\$\{min\}",
                "String ${len} should not be translated": r"\$\{len\}",
                "String ${pattern} should not be translated": r"\$\{pattern\}",
                "String [{{fievent}}] should not be translated": r"\[\{\{fievent\}\}\]",
                "String [{{accBook}}] should not be translated": r"\[\{\{accBook\}\}\]",
            }

            reasons = []  # 用于存储匹配的条目
            matched_strings = []  # 用于存储被识别的字符串
            # Ensure sentence is a string
            sentence_str = str(sentence) if sentence is not None else ""

            for reason, pattern in patterns.items():
                try:
                    matches = re.findall(pattern, sentence_str)
                    if matches:
                        # Avoid adding duplicate reasons if multiple matches for same pattern
                        if reason not in reasons:
                             reasons.append(reason)
                        # Add unique matches for this pattern
                        for match in matches:
                             if match not in matched_strings:
                                  matched_strings.append(match)
                except Exception as e:
                    print(f"Regex error for pattern '{pattern}' on sentence '{sentence_str[:50]}...': {e}")


            return {
                "contains_special_string": bool(reasons),  # 如果 reasons 列表不为空，表示匹配
                "reason": reasons,  # 返回所有匹配条目 (unique reasons)
                "matched_strings": matched_strings  # 返回所有被识别的字符串 (unique matches)
            }

        result = []
        excel_writer = ExcelFileWriter()
        processed_files = []
        output_zip_path = None # Initialize zip path

        if not input_folder:
             return "Error: No folder/files provided.", None

        try:
             folder_path = os.path.dirname(input_folder[0].name) # Get dir from first file
             processed_folder = os.path.join(folder_path, 'processed_glossary_check')
             os.makedirs(processed_folder, exist_ok=True)
        except Exception as e:
             return f"Error creating processed folder: {e}", None


        for input_file in input_folder:
            file_path = input_file.name
            file_name_base = os.path.basename(file_path)
            file_name, file_ext = os.path.splitext(file_name_base)

            if file_ext.lower() == '.xlsx':
                current_end_row = end_row
                try:
                    if row_selection == "所有行":
                        current_end_row = FileReaderFactory.count_rows(file_path)

                    reader, fp = FileReaderFactory.create_reader(file_path) # fp might be None or file pointer
                    original_inputs = reader.extract_text(file_path, original_column, start_row, current_end_row)
                    reference_inputs = reader.extract_text(file_path, reference_column, start_row, current_end_row)
                    translated_inputs = reader.extract_text(file_path, translated_column, start_row, current_end_row)
                    if fp: # Close file pointer if factory returned one
                         fp.close()

                except Exception as e:
                    result.append(f"Error reading {file_name_base}: {e}")
                    continue # Skip to next file

                result.append(f"Checking {file_name_base}:")
                outputs = [] # Remarks to write back to Excel
                max_len = max(len(original_inputs), len(reference_inputs), len(translated_inputs))
                min_len = min(len(original_inputs), len(reference_inputs), len(translated_inputs))
                if max_len != min_len:
                     result.append(f"\tWarning: Column lengths differ ({len(original_inputs)}, {len(reference_inputs)}, {len(translated_inputs)}). Processing up to shortest length: {min_len}")

                for index in range(min_len):
                    original_input = original_inputs[index]
                    reference_input = reference_inputs[index]
                    translated_input = translated_inputs[index]
                    remark = "" # Start with empty remark

                    # Ensure inputs are strings for comparison and analysis
                    original_str = str(original_input) if original_input is not None else ""
                    reference_str = str(reference_input) if reference_input is not None else ""
                    translated_str = str(translated_input) if translated_input is not None else ""


                    special_check_result = contains_special_string(original_str)

                    if special_check_result["contains_special_string"]:
                        missed_matches_info = [] # Store tuples of (missed_string, reason)
                        found_in_translation = True # Assume found initially

                        for matched_string in special_check_result["matched_strings"]:
                            # Check if the specific matched string is missing in translation
                            if matched_string not in translated_str:
                                # If missing in translation, check if it was also missing in reference (optional check)
                                if matched_string not in reference_str:
                                    # Optional: Log or handle cases missing in both ref and translation differently
                                    # print(f"Row {start_row + index}: '{matched_string}' missing in translation and reference.")
                                    pass # Currently, we only penalize if missing in translation but present in original
                                else:
                                    # It's missing in translation but was in original (and reference implies it should be kept)
                                    found_in_translation = False
                                    # Find the reason associated with this specific string (might be multiple reasons)
                                    associated_reasons = [r for r, p in contains_special_string(original_str)["reason"].items() if re.search(p, matched_string)]
                                    reason_text = associated_reasons[0] if associated_reasons else "Unknown reason" # Get first reason
                                    missed_matches_info.append((matched_string, reason_text))


                        if not found_in_translation:
                            # Format the remark string
                            missed_items_str = ', '.join([f"'{info[0]}'" for info in missed_matches_info])
                            reasons_str = ', '.join(set([info[1] for info in missed_matches_info])) # Unique reasons
                            remark += f"MISSED: {missed_items_str}; REASON: {reasons_str}"
                            result.append(
                                f"\tROW: {start_row + index}, MISSED: {missed_items_str}, REASON: {reasons_str}")
                        else:
                             # All special strings found, add a generic remark if needed
                             remark += "SPECIAL_STRINGS_OK"

                    # Token length check (optional, added to remark)
                    try:
                        # Ensure tokenizer is loaded
                        if 'tokenizer' in globals() and tokenizer:
                             token_count = len(tokenizer.encode(original_str))
                             if token_count > 40: # Your threshold
                                 length_remark = "EXCEEDS_40_TOKENS"
                                 if remark: # Append to existing remark
                                     remark += f"; {length_remark}"
                                 else:
                                     remark = length_remark
                                 result.append(f"\tROW: {start_row + index}, {length_remark} ({token_count} tokens)")
                        else:
                            print("Warning: Tokenizer not loaded, skipping length check.")
                    except Exception as e:
                        print(f"Error during tokenization for row {start_row + index}: {e}")


                    outputs.append(remark if remark else "") # Append remark or empty string


                # Ensure outputs list has the correct length (up to min_len)
                if len(outputs) != min_len:
                    print(f"Warning: Length mismatch in remarks generation for {file_name_base}. Expected {min_len}, got {len(outputs)}.")
                    # Pad or truncate if necessary, though ideally loop range handles this.
                    outputs = outputs[:min_len] + [""] * (min_len - len(outputs))


                # Write remarks back to the Excel file
                try:
                    # write_list expects the file path, list of remarks, target column, start row, end row (exclusive?)
                    # Adjust end row for write_list if it's exclusive: current_end_row + 1 ? Check definition.
                    # Assuming end_row in write_list is inclusive index matching read logic.
                    output_file = excel_writer.write_list(file_path, outputs, remark_column, start_row, current_end_row)

                    # Move the modified file to the processed folder
                    processed_file_path = os.path.join(processed_folder, os.path.basename(output_file))
                    # shutil.move might fail if source and destination are the same drive/different mounts sometimes
                    # Safer to copy then delete source, or ensure move works. Let's assume move is ok.
                    shutil.move(output_file, processed_file_path)
                    processed_files.append(processed_file_path)
                    result.append(f"{file_name_base} check completed. Results saved to processed folder.")

                except Exception as e:
                    result.append(f"Error writing remarks or moving file for {file_name_base}: {e}")
                    # Clean up partially written file if possible (output_file might exist)
                    if 'output_file' in locals() and os.path.exists(output_file):
                        try: os.remove(output_file)
                        except OSError: pass


            else:
                result.append(f"Skipping non-Excel file: {file_name_base}")


        # --- Create Zip of Processed Files ---
        if processed_files:
            zip_filename_base = "glossary_check_results.zip"
            output_zip_path = os.path.join(folder_path, zip_filename_base) # Save zip in original upload dir
            try:
                with zipfile.ZipFile(output_zip_path, 'w') as zipf:
                    for file in processed_files:
                        if os.path.exists(file):
                            zipf.write(file, os.path.basename(file))
                            print(f"Adding {os.path.basename(file)} to zip.")
                        else:
                            print(f"Warning: File {file} not found for zipping.")
                result.append(f"Processed files zipped to {zip_filename_base}")
            except Exception as e:
                result.append(f"Error creating zip file: {e}")
                output_zip_path = None # Indicate zip creation failed
        else:
            result.append("No files were processed successfully.")


        return "\n".join(result), output_zip_path # Return status string and path to zip (or None)

    # --- Gradio UI Layout ---
    with gr.Blocks(title="yonyou translator") as interface:
        # Define initial choices based on the default model, if possible
        initial_original_choices = []
        initial_target_choices = []
        initial_lora_choices = ['']
        initial_explanation = "Select a model to see details."

        # Try to pre-populate choices for the default model
        if default_model_name in available_models:
            try:
                 # Call update_choices logic manually once for defaults
                 # This avoids needing a complex Gradio `load` event setup sometimes
                 _model_path = available_models[default_model_name]
                 _sl_path = os.path.join(_model_path, 'support_language.json')
                 _readme_path = os.path.join(_model_path, 'README.md')

                 if os.path.exists(_readme_path):
                      with open(_readme_path, 'r', encoding='utf-8') as f: initial_explanation = f.read()
                 if os.path.exists(_sl_path):
                      with open(_sl_path, 'r') as f:
                           _langs = json.load(f)
                           initial_original_choices = _langs.get("original_language", [])
                           initial_target_choices = _langs.get("target_language", [])
                 try:
                    initial_lora_choices = [''] + [f for f in os.listdir(_model_path) if
                                     os.path.isdir(os.path.join(_model_path, f)) and not f.startswith('.') and not f.startswith('_')]
                 except Exception: pass # Ignore lora errors on initial load

            except Exception as e:
                 print(f"Error pre-loading defaults for {default_model_name}: {e}")
                 # Keep initial_* lists empty/default if error

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
                            # Set default model value here
                            selected_model_excel = gr.Dropdown(choices=list(available_models.keys()), label="选择基模型", value=default_model_name)
                            # Set initial choices and default lora value
                            selected_lora_model_excel = gr.Dropdown(choices=initial_lora_choices, label="选择Lora模型", value='')
                            selected_gpu_excel = gr.Dropdown(choices=available_gpus, label="选择GPU", value=available_gpus[0] if available_gpus else None)
                            batch_size_excel = gr.Number(value=10, label="批处理大小")
                        with gr.Row():
                            # Set initial choices and default language values here
                            original_language_excel = gr.Dropdown(choices=initial_original_choices, label="原始语言", value=default_original_language)
                            target_languages_excel = gr.Dropdown(choices=initial_target_choices, label="目标语言", multiselect=True, value=default_target_language_multi)
                        translate_button_excel = gr.Button("Translate")
                    with gr.Column():
                        # Set initial explanation
                        model_explanation_textbox_excel = gr.Textbox(label="模型介绍", lines=5, value=initial_explanation)
                        output_text_excel = gr.Textbox(label="输出文本")
                        output_file_excel = gr.File(label="翻译文件下载")

                # Link change event
                selected_model_excel.change(update_choices,
                                            inputs=[selected_model_excel],
                                            outputs=[original_language_excel, target_languages_excel, selected_lora_model_excel, model_explanation_textbox_excel])
                # Link click event
                translate_button_excel.click(translate_excel,
                                             inputs=[input_file, start_row, end_row, start_column, target_column,
                                                     selected_model_excel, selected_lora_model_excel, selected_gpu_excel, batch_size_excel,
                                                     original_language_excel, target_languages_excel],
                                             outputs=[output_text_excel, output_file_excel])

            with gr.TabItem("Text Translator"):
                 with gr.Row():
                     with gr.Column():
                         input_text_text = gr.Textbox(label="输入文本", lines=3)
                         with gr.Row():
                              selected_model_text = gr.Dropdown(choices=list(available_models.keys()), label="选择基模型", value=default_model_name)
                              selected_lora_model_text = gr.Dropdown(choices=initial_lora_choices, label="选择Lora模型", value='')
                              selected_gpu_text = gr.Dropdown(choices=available_gpus, label="选择GPU", value=available_gpus[0] if available_gpus else None)
                              batch_size_text = gr.Number(value=1, label="批处理大小", visible=False) # Usually 1 for single text
                         with gr.Row():
                              original_language_text = gr.Dropdown(choices=initial_original_choices, label="原始语言", value=default_original_language)
                              target_languages_text = gr.Dropdown(choices=initial_target_choices, label="目标语言", multiselect=True, value=default_target_language_multi)
                         translate_button_text = gr.Button("Translate")
                     with gr.Column():
                          model_explanation_textbox_text = gr.Textbox(label="模型介绍", lines=5, value=initial_explanation)
                          output_text_text = gr.Textbox(label="输出文本", lines=5)

                 selected_model_text.change(update_choices,
                                           inputs=[selected_model_text],
                                           outputs=[original_language_text, target_languages_text, selected_lora_model_text, model_explanation_textbox_text])
                 translate_button_text.click(translate,
                                            inputs=[input_text_text, selected_model_text, selected_lora_model_text, selected_gpu_text,
                                                    batch_size_text, original_language_text, target_languages_text],
                                            outputs=output_text_text) # Output only to text box


            with gr.TabItem("Folder Excel Translator"):
                with gr.Row():
                    with gr.Column():
                        input_folder_fexcel = gr.File(file_count="directory", label="选择Excel文件所在文件夹")
                        with gr.Row():
                            start_row_fexcel = gr.Number(value=yaml_data["excel_config"]["default_start_row"], label="起始行")
                        with gr.Row():
                            row_selection_fexcel = gr.Radio(choices=["特定行", "所有行"], label="行选择", value="特定行")
                            end_row_fexcel = gr.Number(value=yaml_data["excel_config"]["default_end_row"], label="终止行", visible=True)
                        row_selection_fexcel.change(update_row_selection, inputs=row_selection_fexcel, outputs=end_row_fexcel)
                        with gr.Row():
                            target_column_fexcel = gr.Textbox(value=yaml_data["excel_config"]["default_target_column"], label="目标列")
                            start_column_fexcel = gr.Textbox(value=yaml_data["excel_config"]["default_start_column"], label="结果写入列")
                        with gr.Row():
                            selected_model_fexcel = gr.Dropdown(choices=list(available_models.keys()), label="选择基模型", value=default_model_name)
                            selected_lora_model_fexcel = gr.Dropdown(choices=initial_lora_choices, label="选择Lora模型", value='')
                            selected_gpu_fexcel = gr.Dropdown(choices=available_gpus, label="选择GPU", value=available_gpus[0] if available_gpus else None)
                            batch_size_fexcel = gr.Number(value=yaml_data.get("excel_config", {}).get("default_batch_size", 10), label="批处理大小", visible=True) # Use default from yaml or 10
                        with gr.Row():
                            original_language_fexcel = gr.Dropdown(choices=initial_original_choices, label="原始语言", value=default_original_language)
                            target_languages_fexcel = gr.Dropdown(choices=initial_target_choices, label="目标语言", multiselect=True, value=default_target_language_multi)
                        translate_button_fexcel = gr.Button("Translate Folder")
                    with gr.Column():
                        model_explanation_textbox_fexcel = gr.Textbox(label="模型介绍", lines=5, value=initial_explanation)
                        output_text_fexcel = gr.Textbox(label="处理状态", lines=5)
                        output_folder_fexcel = gr.File(label="下载处理后的Zip文件")

                selected_model_fexcel.change(update_choices,
                                            inputs=[selected_model_fexcel],
                                            outputs=[original_language_fexcel, target_languages_fexcel, selected_lora_model_fexcel, model_explanation_textbox_fexcel])
                translate_button_fexcel.click(translate_excel_folder,
                                            inputs=[input_folder_fexcel, start_row_fexcel, end_row_fexcel, start_column_fexcel, target_column_fexcel,
                                                    selected_model_fexcel, selected_lora_model_fexcel, selected_gpu_fexcel, batch_size_fexcel,
                                                    original_language_fexcel, target_languages_fexcel, row_selection_fexcel],
                                            outputs=[output_text_fexcel, output_folder_fexcel])


            with gr.TabItem("Folder Markdown & Docx Translator"):
                with gr.Row():
                    with gr.Column():
                         # Allow uploading directory or individual files
                        input_folder_mdoc = gr.File(file_count="multiple", file_types=['.md', '.docx', '.pptx'], label="选择Markdown, Docx, PPTX文件或文件夹") # Allow multiple file types
                        with gr.Row():
                            selected_model_mdoc = gr.Dropdown(choices=list(available_models.keys()), label="选择基模型", value=default_model_name)
                            selected_lora_model_mdoc = gr.Dropdown(choices=initial_lora_choices, label="选择Lora模型", value='')
                            selected_gpu_mdoc = gr.Dropdown(choices=available_gpus, label="选择GPU", value=available_gpus[0] if available_gpus else None)
                            batch_size_mdoc = gr.Number(value=5, label="批处理大小", visible=True) # Adjust default batch size as needed
                        with gr.Row():
                            original_language_mdoc = gr.Dropdown(choices=initial_original_choices, label="原始语言", value=default_original_language)
                            # Changed target_language to single select for this tab as per original code structure
                            target_language_mdoc = gr.Dropdown(choices=initial_target_choices, label="目标语言", value=default_target_language_single)
                        translate_button_mdoc = gr.Button("Translate Folder/Files")
                    with gr.Column():
                        model_explanation_textbox_mdoc = gr.Textbox(label="模型介绍", lines=5, value=initial_explanation)
                        output_text_mdoc = gr.Textbox(label="处理状态", lines=5)
                        output_folder_mdoc = gr.File(label="下载处理后的Zip文件")

                selected_model_mdoc.change(update_choices,
                                            inputs=[selected_model_mdoc],
                                            # Ensure target_language_mdoc is updated correctly (might need adjustment in update_choices return if it expects multiselect always)
                                            # Let's assume update_choices returns (orig_lang_dd, target_lang_multi_dd, lora_dd, explanation)
                                            # We map target_lang_multi_dd's choices to the single-select target_language_mdoc
                                            outputs=[original_language_mdoc, target_language_mdoc, selected_lora_model_mdoc, model_explanation_textbox_mdoc]) # Map 2nd output to single dropdown

                # Update click handler inputs/outputs
                translate_button_mdoc.click(translate_markdown_folder,
                                          inputs=[input_folder_mdoc, selected_model_mdoc, selected_lora_model_mdoc, selected_gpu_mdoc,
                                                  batch_size_mdoc, original_language_mdoc, target_language_mdoc], # Pass single target lang
                                          outputs=[output_text_mdoc, output_folder_mdoc])

            with gr.TabItem("术语表校验"):
                 with gr.Row():
                     with gr.Column():
                         input_folder_gloss = gr.File(file_count="directory", label="选择包含待校验Excel文件的文件夹")
                         with gr.Row():
                             row_selection_gloss = gr.Radio(choices=["特定行", "所有行"], label="行选择", value="特定行")
                             start_row_gloss = gr.Number(value=yaml_data["excel_config"]["default_start_row"], label="起始行")
                             end_row_gloss = gr.Number(value=yaml_data["excel_config"]["default_end_row"], label="终止行", visible=True)
                         row_selection_gloss.change(update_row_selection, inputs=row_selection_gloss, outputs=end_row_gloss)
                         with gr.Row():
                              # Use defaults from YAML or hardcode if not present
                              default_orig_col = yaml_data.get("glossary_config", {}).get("original_column", "J")
                              default_ref_col = yaml_data.get("glossary_config", {}).get("reference_column", "G")
                              default_trans_col = yaml_data.get("glossary_config", {}).get("translated_column", "H")
                              default_remark_col = yaml_data.get("glossary_config", {}).get("remark_column", "I")
                              original_column_gloss = gr.Textbox(default_orig_col, label="原文列")
                              reference_column_gloss = gr.Textbox(default_ref_col, label="参考列")
                              translated_column_gloss = gr.Textbox(default_trans_col, label="已翻译列")
                              remark_column_gloss = gr.Textbox(default_remark_col, label="备注写入列")
                         glossary_check_button = gr.Button("开始检测")

                     with gr.Column():
                         output_text_gloss = gr.Textbox(label="检测结果摘要", lines=20, show_copy_button=True)
                         output_folder_gloss = gr.File(label="下载标注后的Zip文件")

                 glossary_check_button.click(glossary_check,
                                            inputs=[input_folder_gloss, start_row_gloss, end_row_gloss, original_column_gloss, reference_column_gloss,
                                                    translated_column_gloss, row_selection_gloss, remark_column_gloss],
                                            outputs=[output_text_gloss, output_folder_gloss])

    return interface


main_ui = webui()

if __name__ == "__main__":
    # Consider adding server_name="0.0.0.0" to allow access from other devices on the network
    main_ui.launch(share=True, server_port=8080) # share=True generates a public link (requires internet)