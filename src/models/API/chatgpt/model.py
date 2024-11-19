from openai import OpenAI
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

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

            else:
                # Find and store any image tags with base64 encoded data
                removed_images = re.findall(r"!\[.*?\]\(data:image\/[^;]+;base64,[^)]+\)", input)
                # Remove the image tags from the text
                input = re.sub(r"!\[.*?\]\(data:image\/[^;]+;base64,[^)]+\)", "", input)

                completion = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": f"You are an expert in translating {original_language} to {target_language} for ERP systems. Your task is to translate markdown-formatted text from {original_language} to {target_language}. The text to be translated may not necessarily be complete phrases or sentences, but you must translate it into the corresponding language based on your own understanding, preserving its formatting without adding extra content."},
                        {"role": "user", "content": input},
                    ],
                    temperature=0
                )
                translated_text = completion.choices[0].message.content
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
