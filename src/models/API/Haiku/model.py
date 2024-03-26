import os
from dotenv import load_dotenv
import anthropic
import math
import csv

class Model():
    def __init__(self, modelname, selected_lora_model, selected_gpu):
        load_dotenv()
        self.client = anthropic.Anthropic(
            api_key=os.getenv("CLAUDE_API_KEY"),
        )
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
        
        batch_size = 100
        results = []
        total_batches = math.ceil(len(inputs) / batch_size)

        for batch_num in range(total_batches):
            start_index = batch_num * batch_size
            end_index = min((batch_num + 1) * batch_size, len(inputs))
            batch_inputs = inputs[start_index:end_index]
            
            prompt = []
            prompt.append({'role': 'user', 'content': '登录日志$$$工作中心分类$$$协作企业登记$$$衍生品合约$$$月度融资到位编制'})
            prompt.append({'role':'assistant', 'content': 'บันทึกการเข้าสู่ระบบ$$$การจำแนกศูนย์ปฏิบัติงาน$$$การลงทะเบียนองค์กรความร่วมมือ$$$สัญญาอนุพันธ์$$$การจัดทำข้อมูลการระดมทุนรายเดือนที่ได้รับ'})
            prompt.append({'role': 'user', 'content': '$$$'.join(batch_inputs)})
            
            message = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=4096,
                temperature=0.1,
                system=f"Converting text from {original_language} to {target_languages}, use $$$ to split different sentences as the example, do not add anything else",
                messages=prompt
            )
            
            translations = message.content[0].text.split('$$$')
            
            for translation in translations:
                result = []
                for target_language in target_languages:
                    result.append({
                        "target_language": target_language,
                        "generated_translation": translation.strip(),
                    })
                results.append(result)
            
            print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
            print(str(len(results))+" finished!")
            
            if len(results) % 100 == 0 or batch_num == total_batches - 1:
                start_row = (len(results) - 1) // 100 * 100 + 1
                end_row = len(results)
                file_name = f"translate_{start_row}_{end_row}.csv"
                
                with open(file_name, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['target_language', 'generated_translation']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    writer.writeheader()
                    for result in results[start_row-1:end_row]:
                        for item in result:
                            writer.writerow(item)

        return results