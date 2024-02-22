from transformers import MBartForConditionalGeneration, MBart50TokenizerFast, AutoModelForSeq2SeqLM, AutoTokenizer, GenerationConfig, pipeline
from abc import ABC, abstractmethod
from typing import Type
import torch
import torch.nn.functional as F
from peft import PeftModel, PeftConfig
from modules.file import ExcelFileWriter

def is_support_lora(model_type):
    if model_type == "t5":
        return True
    return False

def process_gpu_translate_result(temp_outputs, batch_size):
    outputs = []
    for temp_output in temp_outputs:
        length = len(temp_output[0]["generated_translation"])
        for i in range(length):
            temp = []
            for trans in temp_output:
                temp.append({
                    "target_language": trans["target_language"],
                    "generated_translation": trans['generated_translation'][i],
                })
            outputs.append(temp)
    excel_writer = ExcelFileWriter()
    excel_writer.write_text(r"./temp/empty.xlsx", outputs, 'A', 1, batch_size)

def get_gpu_index(gpu_info, target_gpu_name):
    """
    从 GPU 信息中获取目标 GPU 的索引
    Args:
        gpu_info (list): 包含 GPU 名称的列表
        target_gpu_name (str): 目标 GPU 的名称

    Returns:
        int: 目标 GPU 的索引，如果未找到则返回 -1
    """
    for i, name in enumerate(gpu_info):
        if target_gpu_name.lower() in name.lower():
            return i
    return -1

class Model(ABC):
    @abstractmethod
    def __init__(self, modelname, selected_gpu, **kwargs):
        pass
    @abstractmethod
    def generate(self, input, **kwargs) -> str:
        pass
    @abstractmethod
    def fine_tune(self, dict, **kwargs) -> bool:
        pass
    @abstractmethod
    def save(self, path, **kwargs) -> bool:
        pass

class T5Model(Model):
    def __init__(self, modelname, selected_gpu):
        if selected_gpu != "cpu":
            gpu_count = torch.cuda.device_count()
            gpu_info = [torch.cuda.get_device_name(i) for i in range(gpu_count)]
            selected_gpu_index = get_gpu_index(gpu_info, selected_gpu)
            self.device_name = f"cuda:{selected_gpu_index}"
        else:
            self.device_name = "cpu"
        print("device_name", self.device_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(modelname, torch_dtype=torch.bfloat16).to(self.device_name)
        self.tokenizer = AutoTokenizer.from_pretrained(modelname)

    def merge_lora(self, lora_model_path):
        print("lora_model_path", lora_model_path)
        self.model = PeftModel.from_pretrained(self.model, lora_model_path, torch_dtype=torch.bfloat16, is_trainable=False)
        self.tokenizer = AutoTokenizer.from_pretrained(lora_model_path)

    def generate(self, inputs, original_language, target_languages, max_batch_size) -> str:
        m = len(inputs)
        n = len(target_languages)
        outputs = [[None] * n for _ in range(m)]
        for i in range(len(target_languages)):
            prompt = [f"""translate {original_language} to {target_languages[i]}:{input}""" for input in inputs]
            input_ids = self.tokenizer(prompt, return_tensors="pt", padding=True).input_ids.to(self.device_name)
            print("input_ids", input_ids)
            generated_tokens = self.model.generate(input_ids=input_ids, generation_config=GenerationConfig(max_new_tokens=200, num_beams=1))
            for j in range(len(generated_tokens)):
                outputs[j][i] = {
                    "target_language": target_languages[i],
                    "generated_translation": self.tokenizer.decode(generated_tokens[j], skip_special_tokens=True),
                }
        return outputs
    def fine_tune(self, dict, **kwargs) -> bool:
        pass
    def save(self, path, **kwargs) -> bool:
        pass

class NllbModel(Model):
    def __init__(self, modelname, selected_gpu):
        if selected_gpu != "cpu":
            gpu_count = torch.cuda.device_count()
            gpu_info = [torch.cuda.get_device_name(i) for i in range(gpu_count)]
            selected_gpu_index = get_gpu_index(gpu_info, selected_gpu)
            self.device_name = f"cuda:{selected_gpu_index}"
        else:
            self.device_name = "cpu"
        print("device_name", self.device_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(modelname).to(self.device_name)
        self.tokenizer = AutoTokenizer.from_pretrained(modelname)
        # self.translator = pipeline('translation', model=self.original_model, tokenizer=self.tokenizer, src_lang=original_language, tgt_lang=target_language, device=device)

    def language_mapping(self, original_language):
        d = {
            "Achinese": "ace_Latn", # 假设使用拉丁字母脚本的亚齐语
            "Arabic": "ar_AR", # 通用阿拉伯语
            "Bengali": "ben_Beng", # 孟加拉语
            "Bashkir": "bak_Cyrl", # 巴什基尔语，使用西里尔字母
            "Belarusian": "bel_Cyrl", # 白俄罗斯语
            "Bambara": "bam_Latn", # 班巴拉语
            "Bulgarian": "bul_Cyrl", # 保加利亚语
            "Czech": "ces_Latn", # 捷克语
            "Chinese": "zho_Hans", # 简体中文
            "Spanish": "spa_Latn",
            "Dutch": "nld_Latn", # 荷兰语
            "English": "eng_Latn", # 英语
            "French": "fra_Latn", # 法语
            "German": "deu_Latn", # 德语
            "Gujarati": "guj_Gujr", # 古吉拉特语
            "Hebrew": "heb_Hebr", # 希伯来语
            "Hindi": "hin_Deva", # 印地语
            "Italian": "ita_Latn", # 意大利语
            "Japanese": "jpn_Jpan", # 日语
            "Kazakh": "kaz_Cyrl", # 哈萨克语
            "Korean": "kor_Hang", # 韩语
            "Lithuanian": "lit_Latn", # 立陶宛语
            "Malayalam": "mal_Mlym", # 马拉雅拉姆语
            "Marathi": "mar_Deva", # 马拉地语
            "Nepali": "ne_NP", # 尼泊尔语
            "Persian": "pes_Arab", # 波斯语
            "Polish": "pol_Latn", # 波兰语
            "Portuguese": "pt_XX", # 葡萄牙语
            "Russian": "rus_Cyrl", # 俄语
            "Sinhala": "sin_Sinh", # 僧伽罗语
            "Tamil": "tam_Taml", # 泰米尔语
            "Turkish": "tur_Latn", # 土耳其语
            "Ukrainian": "ukr_Cyrl", # 乌克兰语
            "Urdu": "urd_Arab", # 乌尔都语
            "Vietnamese": "vie_Latn", # 越南语
        }
        return d[original_language]
    
    def generate(self, inputs, original_language, target_languages, max_batch_size):
        # Estimate batch size based on memory usage
        self.tokenizer.src_lang = self.language_mapping(original_language)
        if self.device_name == "cpu":
            # Tokenize input
            input_ids = self.tokenizer(inputs, return_tensors="pt", padding=True).to(self.device_name)
            output = []
            for target_language in target_languages:
                # Get language code for the target language
                target_lang_code = self.tokenizer.lang_code_to_id[self.language_mapping(target_language)]
                # Generate translation
                generated_tokens = self.model.generate(
                    **input_ids,
                    forced_bos_token_id=target_lang_code
                )
                generated_translation = self.tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)
                # Append result to output
                output.append({
                    "target_language": target_language,
                    "generated_translation": generated_translation,
                })
            outputs = []
            length = len(output[0]["generated_translation"])
            for i in range(length):
                temp = []
                for trans in output:
                    temp.append({
                        "target_language": trans["target_language"],
                        "generated_translation": trans['generated_translation'][i],
                    })
                outputs.append(temp)
            return outputs
        else:
            # 最大批量大小 = 可用 GPU 内存字节数 / 4 / （张量大小 + 可训练参数）
            # max_batch_size = 10
            # Ensure batch size is within model limits:
            batch_size = min(len(inputs), int(max_batch_size))
            batches = [inputs[i:i + batch_size] for i in range(0, len(inputs), batch_size)]
            temp_outputs = []
            processed_num = 0
            for index, batch in enumerate(batches):
                # Tokenize input
                input_ids = self.tokenizer(batch, return_tensors="pt", padding=True).to(self.device_name)
                temp = []
                for target_language in target_languages:
                    # Get language code for the target language
                    target_lang_code = self.tokenizer.lang_code_to_id[self.language_mapping(target_language)]
                    # Extract probability for the target language
                    generated_tokens = self.model.generate(
                        **input_ids,
                        forced_bos_token_id=target_lang_code,
                    )
                    generated_translation = self.tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)
                    # Append result to output
                    temp.append({
                        "target_language": target_language,
                        "generated_translation": generated_translation,
                    })
                input_ids.to('cpu')
                del input_ids
                temp_outputs.append(temp)
                processed_num += len(batch)
                if (index + 1) * max_batch_size % 1000 == 0:
                    print("Already processed number: ", int((index + 1) * max_batch_size))
                    process_gpu_translate_result(temp_outputs, (index + 1) * max_batch_size)
            outputs = []
            for temp_output in temp_outputs:
                length = len(temp_output[0]["generated_translation"])
                for i in range(length):
                    temp = []
                    for trans in temp_output:
                        temp.append({
                            "target_language": trans["target_language"],
                            "generated_translation": trans['generated_translation'][i],
                        })
                    outputs.append(temp)
            return outputs
    def fine_tune(self, dict, **kwargs) -> bool:
        pass
    def save(self, path, **kwargs) -> bool:
        pass
    
class MBartModel(Model):
    def __init__(self, modelname, selected_gpu):
        if selected_gpu != "cpu":
            gpu_count = torch.cuda.device_count()
            gpu_info = [torch.cuda.get_device_name(i) for i in range(gpu_count)]
            selected_gpu_index = get_gpu_index(gpu_info, selected_gpu)
            self.device_name = f"cuda:{selected_gpu_index}"
        else:
            self.device_name = "cpu"
        print("device_name", self.device_name)
        self.model = MBartForConditionalGeneration.from_pretrained(modelname).to(self.device_name)
        self.tokenizer = MBart50TokenizerFast.from_pretrained(modelname)

    def language_mapping(self, original_language):
        d = {
            "Arabic": "ar_AR",
            "Czech": "cs_CZ",
            "German": "de_DE",
            "English": "en_XX",
            "Spanish": "es_XX",
            "Estonian": "et_EE",
            "Finnish": "fi_FI",
            "French": "fr_XX",
            "Gujarati": "gu_IN",
            "Hindi": "hi_IN",
            "Italian": "it_IT",
            "Japanese": "ja_XX",
            "Kazakh": "kk_KZ",
            "Korean": "ko_KR",
            "Lithuanian": "lt_LT",
            "Latvian": "lv_LV",
            "Burmese": "my_MM",
            "Nepali": "ne_NP",
            "Dutch": "nl_XX",
            "Romanian": "ro_RO",
            "Russian": "ru_RU",
            "Sinhala": "si_LK",
            "Turkish": "tr_TR",
            "Vietnamese": "vi_VN",
            "Chinese": "zh_CN",
            "Afrikaans": "af_ZA",
            "Azerbaijani": "az_AZ",
            "Bengali": "bn_IN",
            "Persian": "fa_IR",
            "Hebrew": "he_IL",
            "Croatian": "hr_HR",
            "Indonesian": "id_ID",
            "Georgian": "ka_GE",
            "Khmer": "km_KH",
            "Macedonian": "mk_MK",
            "Malayalam": "ml_IN",
            "Mongolian": "mn_MN",
            "Marathi": "mr_IN",
            "Polish": "pl_PL",
            "Pashto": "ps_AF",
            "Portuguese": "pt_XX",
            "Swedish": "sv_SE",
            "Swahili": "sw_KE",
            "Tamil": "ta_IN",
            "Telugu": "te_IN",
            "Thai": "th_TH",
            "Tagalog": "tl_XX",
            "Ukrainian": "uk_UA",
            "Urdu": "ur_PK",
            "Xhosa": "xh_ZA",
            "Galician": "gl_ES",
            "Slovene": "sl_SI"
        }
        return d[original_language]

    def generate(self, inputs, original_language, target_languages, max_batch_size):
        if original_language != "English":
            raise ValueError("Unsupported original language. Only 'English' is allowed.")
        # Estimate batch size based on memory usage
        if self.device_name == "cpu":
            # Tokenize input
            input_ids = self.tokenizer(inputs, return_tensors="pt", padding=True).to(self.device_name)
            output = []
            for target_language in target_languages:
                # Generate logits
                with torch.no_grad():
                    logits = self.model(**input_ids).logits
                # Get language code for the target language
                target_lang_code = self.tokenizer.lang_code_to_id[self.language_mapping(target_language)]
                # Generate translation
                generated_tokens = self.model.generate(
                    **input_ids,
                    forced_bos_token_id=target_lang_code
                )
                generated_translation = self.tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)
                # Append result to output
                output.append({
                    "target_language": target_language,
                    "generated_translation": generated_translation,
                })
            outputs = []
            length = len(output[0]["generated_translation"])
            for i in range(length):
                temp = []
                for trans in output:
                    temp.append({
                        "target_language": trans["target_language"],
                        "generated_translation": trans['generated_translation'][i],
                    })
                outputs.append(temp)
            return outputs
        else:
            # 最大批量大小 = 可用 GPU 内存字节数 / 4 / （张量大小 + 可训练参数）
            # max_batch_size = 10
            # Ensure batch size is within model limits:
            batch_size = min(len(inputs), int(max_batch_size))
            batches = [inputs[i:i + batch_size] for i in range(0, len(inputs), batch_size)]
            temp_outputs = []
            processed_num = 0
            for index, batch in enumerate(batches):
                # Tokenize input
                input_ids = self.tokenizer(batch, return_tensors="pt", padding=True).to(self.device_name)
                temp = []
                for target_language in target_languages:
                    with torch.no_grad():
                        logits = self.model(**input_ids).logits
                    # Get language code for the target language
                    target_lang_code = self.tokenizer.lang_code_to_id[self.language_mapping(target_language)]
                    # Extract probability for the target language
                    target_lang_prob = F.softmax(logits[0, -1, :])  # Assuming the last token is the target language token
                    target_lang_prob = target_lang_prob[target_lang_code].item()
                    generated_tokens = self.model.generate(
                        **input_ids,
                        forced_bos_token_id=target_lang_code,
                    )
                    generated_translation = self.tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)
                    # Append result to output
                    temp.append({
                        "target_language": target_language,
                        "generated_translation": generated_translation,
                    })
                input_ids.to('cpu')
                del input_ids
                temp_outputs.append(temp)
                processed_num += len(batch)
                if (index + 1) * max_batch_size % 1000 == 0:
                    print("Already processed number: ", int((index + 1) * max_batch_size))
                    process_gpu_translate_result(temp_outputs, (index + 1) * max_batch_size)
            outputs = []
            for temp_output in temp_outputs:
                length = len(temp_output[0]["generated_translation"])
                for i in range(length):
                    temp = []
                    for trans in temp_output:
                        temp.append({
                            "target_language": trans["target_language"],
                            "generated_translation": trans['generated_translation'][i],
                        })
                    outputs.append(temp)
            return outputs
    def fine_tune(self, dict, **kwargs) -> bool:
        pass
    def save(self, path, **kwargs) -> bool:
        pass
    
class ModelFactory:
    @staticmethod
    def create_model(model_type, modelname, selected_gpu, **kwargs) -> Type[Model]:
        model_mapping = {
            "mbart": MBartModel,
            "t5": T5Model, 
            "nllb": NllbModel,
        }
        model_class = model_mapping.get(model_type)

        if model_class:
            return model_class(modelname, selected_gpu, **kwargs)
        else:
            raise ValueError(f"Unsupported model type: {model_type}")