from dotenv import load_dotenv
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
load_dotenv()
client = OpenAI()
import re

# 文件路径
filelist = [
    r"C:\Users\wangz\Desktop\translation\new multilangInitData YS全量词条 20241119\multilangInitData YS全量词条 20241119_part_1_20002_100001_translated.txt",
    r"C:\Users\wangz\Desktop\translation\new multilangInitData YS全量词条 20241119\multilangInitData YS全量词条 20241119_part_2_1_100001_translated.txt",
    r"C:\Users\wangz\Desktop\translation\new multilangInitData YS全量词条 20241119\multilangInitData YS全量词条 20241119_part_3_1_100001_translated.txt",
    r"C:\Users\wangz\Desktop\translation\new multilangInitData YS全量词条 20241119\multilangInitData YS全量词条 20241119_part_4_2_100001_translated.txt",
    r"C:\Users\wangz\Desktop\translation\new multilangInitData YS全量词条 20241119\multilangInitData YS全量词条 20241119_part_5_2_100001_translated.txt",
    r"C:\Users\wangz\Desktop\translation\new multilangInitData YS全量词条 20241119\multilangInitData YS全量词条 20241119_part_6_2_100001_translated.txt",
    r"C:\Users\wangz\Desktop\translation\new multilangInitData YS全量词条 20241119\multilangInitData YS全量词条 20241119_part_7_2_100001_translated.txt",
    r"C:\Users\wangz\Desktop\translation\new multilangInitData YS全量词条 20241119\multilangInitData YS全量词条 20241119_part_8_2_100001_translated.txt",
    r"C:\Users\wangz\Desktop\translation\new multilangInitData YS全量词条 20241119\multilangInitData YS全量词条 20241119_part_9_2_100001_translated.txt",
    r"C:\Users\wangz\Desktop\translation\new multilangInitData YS全量词条 20241119\multilangInitData YS全量词条 20241119_part_10_2_100001_translated.txt",
    r"C:\Users\wangz\Desktop\translation\new multilangInitData YS全量词条 20241119\multilangInitData YS全量词条 20241119_part_11_2_3638_translated.txt"
]
for file_path in filelist:
    # 读取文件内容
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    # 使用正则表达式按照分隔符划分
    parts = content.split("\n")

    pattern = r"ROW\s*:\s*(\d+),\s*MISSED\s*:\s*(.*?),\s*REASON\s*:\s*(.*)"

    to_fix = []
    for part in parts:
        match = re.match(pattern, part)
        row = match.group(1)
        missed = match.group(2)
        reason = match.group(3)
        to_fix.append([row, missed.split(','), reason.split(',')])
        # print("ROW:", row)
        # print("MISSED:", missed)
        # print("REASON:", reason)

    import pandas as pd
    df = pd.read_excel(file_path.replace(".txt", ".xlsx"))

    def generate_text(data):
        index = int(data[0])
        missed = data[1]
        reason = data[2]
        if str(df['参考语言(英文)'][index-2]).strip() == str(df['简体中文(源)'][index-2]).strip():
            return index-2, str(df['参考语言(英文)'][index-2]).strip()
        else:
            try:
                completion = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "user", "content": "Translate English: The received L/G %s is not submitted \nTo Spanish: El L/G recibido no se ha enviado. \nPlease fix the translate error, because %s is missing, translate it directly and without adding any extra content."},
                        {"role": "assistant", "content": "El L/G recibido %s no se ha enviado."},
                        {"role": "user", "content": f"Translate English: {str(df['参考语言(英文)'][index-2])} \nTo Spanish: {str(df['待翻译(译)'][index-2])} \n Please fix the translate error, {'.'.join(['because' + str(a) +'is missing, '+str(b) for a, b in zip(missed, reason)])}. translate it directly and without adding any extra content."}
                    ],
                    temperature=0
                )
                return index-2, completion.choices[0].message.content
            except:
                print(str(df['参考语言(英文)'][index-2]), str(df['待翻译(译)'][index-2]))
                return index-2, str(df['待翻译(译)'][index-2])
        
    from tqdm import tqdm
    with ThreadPoolExecutor(max_workers=1000) as executor:
        futures = {executor.submit(generate_text, data) for data in to_fix}

        for future in tqdm(as_completed(futures), total=len(futures)):
            index, output = future.result()

            if output is not None:
                df.at[index, f'待翻译(译)'] = output

    # 保存最终结果到 Excel 文件
    df.to_excel(file_path.replace(r"C:\Users\wangz\Desktop\translation", r"D:\Projects\ai-translator\src").replace(".txt", ".xlsx"), index=False)
