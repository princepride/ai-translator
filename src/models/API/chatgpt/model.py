from openai import OpenAI
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import pandas as pd

dic = pd.read_excel(r"D:\Projects\ai-translator\src\models\API\chatgpt\glossary.xlsx")

def find_translations(input_text):
    # 用于存储匹配结果
    results = []
    # 遍历术语库，找出中文词及其对应的西班牙语翻译
    for _, row in dic.iterrows():
        chinese_term = row['Chinese']
        spanish_term = row['Spanish']
        if chinese_term in input_text:
            results.append((chinese_term, spanish_term))
    return results

def contains_special_string(sentence):
    # 定义特殊字符串的正则表达式模式字典
    patterns = {
        "<% ... %>": r"<%.*?%>",                                                        # 匹配 <% ... %>
        "%s": r"%s",                                                                    # 匹配 %s
        "{0}, {1}, {2} 等": r"{\d+}",                                                   # 匹配 {0}, {1}, {2} 等
        "%d": r"%d",                                                                    # 匹配 %d
        "{counts}": r"{counts}",                                                        # 匹配 {counts}
        "&{...}&": r"&{.*?}&",                                                          # 匹配 &{...}&
        "{}": r"{}",                                                                    # 匹配 {}
        "#...#": r"#.*?#",                                                              # 匹配 #...#
        "{{...}}": r"{{.*?}}",                                                          # 匹配 {{...}}
        "连续的大写英文字母（AR, AP, SKU）": r"[A-Z]{2,}",                            # 匹配连续的大写英文字母
        "大驼峰命名的单词（如 ServiceCode, LocStudio）": r"(?:[A-Z][a-z]+){2,}",        # 匹配大驼峰命名的单词
        "包含 http:// 的字符串": r"http://",                                             # 匹配包含 "http://"
        "包含 https:// 的字符串": r"https://",                                           # 匹配包含 "https://"
        "包含 E:\, D:\, C:\ 的字符串": r"[CDE]:\\",                                     # 匹配包含 "E:\", "D:\", "C:\"
        "包含 datediff(.*?,.*?,.*?) 的字符串": r"datediff\(.*?,.*?,.*?\)",               # 匹配 datediff
        "@业务函数. ... 的字符串@": r"@业务函数\..*?@",                                  # 匹配 @业务函数. ... 的字符串@
        "小驼峰命名的单词（如 serviceCode, locStudio）": r"[a-z]+[a-z]*[A-Z][a-zA-Z]*"  # 匹配小驼峰命名的单词
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
        "reason": reasons,                         # 返回所有匹配条目
        "matched_strings": matched_strings         # 返回所有被识别的字符串
    }

load_dotenv()

class Model():
    def __init__(self, modelname, selected_lora_model, selected_gpu):
        self.client = OpenAI()

    def translate_section(self, input, original_language, target_languages):
        res = []
        for target_language in target_languages:
            if input.strip().startswith("[ref1]"):
                res.append({
                    "target_language":target_language,
                    "generated_translation":input
                })
            elif not re.search(r'[A-Za-z\u4e00-\u9fff]', input.strip()):
                res.append({
                    "target_language":target_language,
                    "generated_translation":input
                })
            elif input.strip() == "此词条确认无需翻译或已废弃" or input.strip() == "!!!!!!!!" or input.strip() == "Obsolete" or input.strip() == "obsolete":
                res.append({
                    "target_language":target_language,
                    "generated_translation":input
                })
            else:
                # Find and store any image tags with base64 encoded data
                removed_images = re.findall(r"!\[.*?\]\(data:image\/[^;]+;base64,[^)]+\)", input)
                # Remove the image tags from the text
                input = re.sub(r"!\[.*?\]\(data:image\/[^;]+;base64,[^)]+\)", "", input)

                # matches = find_translations(input)
                # terminology_guide = "\n".join([f"- {item1}: {item2}" for item1, item2 in matches])
                # system_prompt = f"""
                # You are an expert in translating {original_language} to {target_language} for ERP systems. Your task is to translate markdown-formatted text from {original_language} to {target_language}.
                        
                # Here is a terminology guide to help you ensure accurate translations for common ERP terms:
                # {terminology_guide}

                # The text to be translated may not necessarily be complete phrases or sentences, but you must translate it into the corresponding language based on your own understanding. Preserving its formatting without adding extra content.
                # """

                system_prompt = f"""
                You are an expert in translating {original_language} to {target_language} for ERP systems. Your task is to translate markdown-formatted text from {original_language} to {target_language}.
                The text to be translated may not necessarily be complete phrases or sentences, but you must translate it into the corresponding language based on your own understanding. Preserving its formatting without adding extra content.
                """

                messages = [{"role": "system", "content": system_prompt}]

                special_string_list = []
                for i in range(2):
                    if i == 0:
                        messages.append({"role": "user", "content": input})
                    else:
                        messages.append({"role": "user", "content": f"You should skip the words: {', '.join(special_string_list)} do not translate, please translate it again without adding extra content."})
                    
                    completion = self.client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        temperature=0
                    )
                    translated_text = completion.choices[0].message.content
                    messages.append({"role": "assistant", "content": translated_text})
                    
                    temp = contains_special_string(input)
                    if temp["contains_special_string"]:
                        all_special_strings_retained = True
                        for matched_string in temp["matched_strings"]:
                            if matched_string not in translated_text:
                                all_special_strings_retained = False
                                if matched_string not in special_string_list:
                                    special_string_list.append(matched_string)
                        if all_special_strings_retained:
                            break
                    else:
                        break
                if removed_images:
                    translated_text += "\n" + "\n".join(removed_images)
                res.append({
                    "target_language":target_language,
                    "generated_translation":translated_text
                })
        return res

    def generate(self, inputs, original_language, target_languages, max_batch_size):
        """
            return sample:
            [
                [
                    {
                        "target_language":"English",
                        "generated_translation":"I love you",
                    },
                    {
                        "target_language":"Chinese",
                        "generated_translation":"我爱你",
                    },
                ],
                [
                    {
                        "target_language":"English",
                        "generated_translation":"Who's your daddy",
                    },
                    {
                        "target_language":"Chinese",
                        "generated_translation":"谁是你爸爸",
                    },
                ],
                [
                    {
                        "target_language":"English",
                        "generated_translation":"Today is Friday",
                    },
                    {
                        "target_language":"Chinese",
                        "generated_translation":"今天是星期五",
                    },
                ],
            ]
        """
        res = [None] * len(inputs)
        with ThreadPoolExecutor(max_workers=1000) as executor:
            futures = {executor.submit(self.translate_section, inputs[i], original_language, target_languages): i for i in range(len(inputs))}
            for future in as_completed(futures):
                index = futures[future]
                try:
                    res[index] = future.result()
                except Exception as e:
                    res[index] = [{"target_language":target_language,"generated_translation":f"Error: {e}"} for target_language in target_languages]
        return res
