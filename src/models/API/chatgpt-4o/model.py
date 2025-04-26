from openai import OpenAI
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import pandas as pd
import numpy as np
import os

glossary_df = pd.read_excel(r"D:\Projects\ai-translator\src\models\API\chatgpt-4o-mini\glossary.xlsx")

import re
import pandas as pd

def find_translations(input_text, original_language, target_language):
    # 如果 original_language 或 target_language 不是列名，则直接返回空列表
    if original_language not in glossary_df.columns or target_language not in glossary_df.columns:
        return []
    
    # 过滤掉原始术语或目标术语为空的行，使用向量化方法构建字典
    valid_entries = glossary_df[glossary_df[original_language].notna() & glossary_df[target_language].notna()]
    term_dict = dict(zip(valid_entries[original_language], valid_entries[target_language]))
    
    # 构建正则表达式，利用 re.escape 对每个术语转义，再用 "|" 拼接起来
    if not term_dict:
        return []
    
    pattern = re.compile("|".join(map(re.escape, term_dict.keys())))
    
    # 使用正则表达式查找所有匹配项，结果可能包含重复匹配
    found_terms = set(pattern.findall(input_text))
    
    # 根据匹配到的术语，构造结果列表
    results = [(term, term_dict[term]) for term in found_terms]
    return results


def contains_special_string(sentence):
    # 定义特殊字符串的正则表达式模式字典
    patterns = {
    # 通用模板语法匹配
    "模板语法 <% ... %>": r"<%.*?%>",                          # 如：<% if (x > 0) { %>
    "字符串占位符 %s": r"%s",                                  # 如："Hello %s"
    "字符串占位符 %d": r"%d",                                  # 如："You have %d messages"
    "Python格式化 {0}, {1}, ...": r"{\d+}",                   # 如："Value: {0}, {1}"
    "命名占位符 {counts}": r"{counts}",                        # 如："Total: {counts}"
    "空模板占位符 {}": r"{}",                                  # 如："{} + {} = {}"
    "自定义标记 &{...}&": r"&{.*?}&",                          # 如："&{username}& logged in"
    "注释/变量标记 #...#": r"#.*?#",                           # 如："#comment#", "#name#"
    "双大括号模板 {{...}}": r"{{.*?}}",                        # 如："{{username}}"
    "@业务函数调用语法@": r"@业务函数\..*?@",                  # 如："@业务函数.计算金额@"

    # 路径 / URL 类型匹配
    "包含 http:// URL": r"http://",                            # 如："http://example.com"
    "包含 https:// URL": r"https://",                          # 如："https://example.com"
    "Windows 路径（E:\\、D:\\、C:\\）": r"[CDE]:\\",          # 如："D:\\data\\file.txt"

    # SQL / 函数调用语法
    "SQL datediff 函数": r"datediff\(.*?,.*?,.*?\)",           # 如："datediff(day, '2024-01-01', '2024-02-01')"

    # 命名规则匹配
    "连续的大写英文字母（如 AR、AP、SKU）": r"[A-Z]{2,}",       # 如："AR", "SKU", "AP"
    "大驼峰命名（如 ServiceCode, LocStudio）": r"(?:[A-Z][a-z]+){2,}",  # 大写开头的复合词
    "小驼峰命名（如 serviceCode, locStudio）": r"[a-z]+[a-z]*[A-Z][a-zA-Z]*",  # 小写开头，包含大写中缀
    "蛇形命名（如 test_engine, user_id）": r"[a-z]+(?:_[a-z]+)+",  # 如："test_engine", "user_id"
    "Pascal 蛇形命名（如 Test_Engine, User_ID）": r"(?:[A-Z][a-zA-Z0-9]*_)+[A-Z][a-zA-Z0-9]*",

    # 特定模板变量（用于校验模板数据）
    "模板变量 ${label}": r"\$\{label\}",                       # 如："${label}"，字段名称
    "模板变量 [${enum}]": r"\[\$\{enum\}\]",                   # 如："[${enum}]"，枚举字段
    "模板变量 ${max}": r"\$\{max\}",                           # 最大值字段
    "模板变量 ${min}": r"\$\{min\}",                           # 最小值字段
    "模板变量 ${len}": r"\$\{len\}",                           # 长度字段
    "模板变量 ${pattern}": r"\$\{pattern\}",                   # 正则表达式字段

    # 可选通配符（如果需要支持所有 ${...}）：
    "通用模板变量 ${...}": r"\$\{.*?\}",                       # 匹配所有形如 ${xxx} 的变量
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
        naming_patterns = [
            r"^[A-Z]{2,}$",  # 连续的大写字母，如 AR、SKU
            r"^(?:[A-Z][a-z]*|[A-Z]{2,}){2,}$",  # 大驼峰命名，如 ServiceCode
            r"^[a-z]+[a-z]*[A-Z][a-zA-Z]*$",  # 小驼峰命名，如 serviceCode
            r"^[a-z]+(?:_[a-z]+)+$",  # 蛇形命名，如 test_engine
            r"^(?:[A-Z][a-zA-Z0-9]*_)+[A-Z][a-zA-Z0-9]*$",  # Pascal 蛇形命名，如 Test_Engine
            r"^(?:[a-z_][a-z0-9_]*\.)+[A-Z][a-zA-Z0-9]*$",  # Java 包名格式，如 com.xxx.MyClass
        ]

        def is_single_token_naming_style(input: str) -> bool:
            stripped = input.strip()
            if " " in stripped:  # 确保是一个单词，没有空格
                return False
            return any(re.fullmatch(pattern, stripped) for pattern in naming_patterns)
        for target_language in target_languages:
            if input.strip().startswith("[ref1]"):
                res.append({
                    "target_language":target_language,
                    "generated_translation":input,
                })
            elif input.strip().startswith("https://") or input.strip().startswith("http://") or is_single_token_naming_style(input):
                res.append({
                    "target_language":target_language,
                    "generated_translation":input,
                })
            elif input.strip() == "":
                res.append({
                    "target_language":target_language,
                    "generated_translation":input,
                })
            elif not re.search(r'[A-Za-z\u4e00-\u9fff]', input.strip()):
                res.append({
                    "target_language":target_language,
                    "generated_translation":input,
                })
            elif input.strip() == "此词条确认无需翻译或已废弃" or input.strip() == "!!!!!!!!" or input.strip() == "Obsolete" or input.strip() == "obsolete":
                res.append({
                    "target_language":target_language,
                    "generated_translation":input,
                })
            else:
                # Find and store any image tags with base64 encoded data
                removed_images = re.findall(r"!\[.*?\]\(data:image\/[^;]+;base64,[^)]+\)", input)
                # Remove the image tags from the text
                input = re.sub(r"!\[.*?\]\(data:image\/[^;]+;base64,[^)]+\)", "", input)

                matches = find_translations(input, original_language, target_language)
                terminology_guide = "\n".join([f"- {item1}: {item2}" for item1, item2 in matches])
                if len(matches) > 0:
                    system_prompt = f"""
                    You are an expert in translating {original_language} to {target_language} for ERP systems. Your task is to translate it from {original_language} to {target_language}.
                            
                    Here is a terminology guide to help you ensure accurate translations for common ERP terms:
                    {terminology_guide}

                    The text to be translated may not necessarily be complete phrases or sentences, but you must translate it into the corresponding language based on your own understanding. Preserving its formatting without adding extra content.
                    """
                else:
                    system_prompt = f"""
                    You are an expert in translating {original_language} to {target_language} for ERP systems. Your task is to translate it from {original_language} to {target_language}.

                    The text to be translated may not necessarily be complete phrases or sentences, but you must translate it into the corresponding language based on your own understanding. Preserving its formatting without adding extra content.
                    """

                # system_prompt = f"""
                # You are an expert in translating {original_language} to {target_language} for ERP systems. Your task is to translate markdown-formatted text from {original_language} to {target_language}.
                # The text to be translated may not necessarily be complete phrases or sentences, but you must translate it into the corresponding language based on your own understanding. Preserving its formatting without adding extra content.
                # """

                messages = [{"role": "system", "content": system_prompt}]

                special_string_list = []
                for i in range(2):
                    if i == 0:
                        messages.append({"role": "user", "content": input})
                    else:
                        messages.append({
                            "role": "user",
                            "content": f"Wrong! You should maintain the words: {', '.join(special_string_list)} do not translate. please translate it again: {input}"
                        })
                    
                    temp = contains_special_string(input)
                    completion = self.client.chat.completions.create(
                        model="gpt-4o",
                        messages=messages,
                        temperature=0,
                    )
                    translated_text = completion.choices[0].message.content
                    messages.append({"role": "assistant", "content": translated_text})

                    # 检查是否包含特殊错误消息
                    error_messages = [
                        "Sorry, I can't assist with that request",
                        "It seems like your message is incomplete",
                        "Error: Connection error"
                        ""
                    ]
                    if any(error_msg in translated_text for error_msg in error_messages):
                        continue  # 重新进入循环进行翻译
                    if "id" in input or "ID" in input:
                        break
                    
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

                translated_text = re.sub(r'[\u4e00-\u9fff]', '', translated_text)
                res.append({
                    "target_language":target_language,
                    "generated_translation":translated_text,
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
        with ThreadPoolExecutor(max_workers=2000) as executor:
            futures = {executor.submit(self.translate_section, inputs[i], original_language, target_languages): i for i in range(len(inputs))}
            for future in as_completed(futures):
                index = futures[future]
                try:
                    res[index] = future.result()
                except Exception as e:
                    res[index] = [{"target_language":target_language,"generated_translation":f"Error: {e}"} for target_language in target_languages]
        return res
