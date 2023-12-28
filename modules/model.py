from transformers import MBartForConditionalGeneration, MBart50TokenizerFast, AutoModelForSeq2SeqLM, AutoTokenizer
from abc import ABC, abstractmethod
from typing import Type
import torch
import torch.nn.functional as F

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
        self.model = AutoModelForSeq2SeqLM.from_pretrained(modelname).to(self.device_name)
        self.tokenizer = AutoTokenizer.from_pretrained(modelname)
    def generate(self, inputs, original_language, target_languages) -> str:
        m = len(inputs)
        n = len(target_languages)
        outputs = [[None] * n for _ in m]
        for i in range(len(target_languages)):
            prompt = [f"""translate {original_language} to {target_languages[i]}:{input}""" for input in inputs]
            input_ids = self.tokenizer(prompt, return_tensors="pt").input_ids
            generated_tokens = self.model.generate(input_ids)
            for j in range(len(generated_tokens)):
                outputs[j][i] = {
                    "target_language": target_languages[i],
                    "generated_translation": self.tokenizer.decode(generated_tokens[j]),
                }
        return outputs
    @abstractmethod
    def fine_tune(self, dict, **kwargs) -> bool:
        pass
    @abstractmethod
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
    
    # def generate(self, input, original_language, target_languages):
    #     assert original_language == "English"
    #     # Tokenize input
    #     input_ids = self.tokenizer(input, return_tensors="pt").to(self.device_name)
    #     output = []
    #     for target_language in target_languages:
    #         # Generate logits
    #         with torch.no_grad():
    #             logits = self.model(**input_ids).logits
    #         # Get language code for the target language
    #         target_lang_code = self.tokenizer.lang_code_to_id[self.language_mapping(target_language)]
    #         # Extract probability for the target language
    #         target_lang_prob = F.softmax(logits[0, -1, :])  # Assuming the last token is the target language token
    #         target_lang_prob = target_lang_prob[target_lang_code].item()
    #         # Generate translation
    #         generated_tokens = self.model.generate(
    #             **input_ids,
    #             forced_bos_token_id=target_lang_code
    #         )
    #         generated_translation = self.tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)
    #         # Append result to output
    #         output.append({
    #             "target_language": target_language,
    #             "generated_translation": generated_translation,
    #             "target_language_probability": target_lang_prob
    #         })
    #     return output

    def generate(self, inputs, original_language, target_languages):
        assert original_language == "English"
        # Estimate batch size based on memory usage
        if self.device_name == "cpu":
            # Tokenize input
            input_ids = self.tokenizer(inputs, return_tensors="pt").to(self.device_name)
            output = []
            for target_language in target_languages:
                # Generate logits
                with torch.no_grad():
                    logits = self.model(**input_ids).logits
                # Get language code for the target language
                target_lang_code = self.tokenizer.lang_code_to_id[self.language_mapping(target_language)]
                # Extract probability for the target language
                target_lang_prob = F.softmax(logits[0, -1, :])  # Assuming the last token is the target language token
                target_lang_prob = target_lang_prob[target_lang_code].item()
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
                    "target_language_probability": target_lang_prob
                })
            return output
        else:
            available_memory = torch.cuda.get_device_properties(self.device_name).total_memory
            max_tokens_per_batch = available_memory // self.model.config.max_length // 4  # Approximate memory usage
            max_batch_size = max_tokens_per_batch // self.model.config.max_position_embeddings
            batch_size = min(len(inputs), max_batch_size)
            batches = [inputs[i:i + batch_size] for i in range(0, len(inputs), batch_size)]
            temp_outputs = []
            for batch in batches:
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
                        "target_language_probability": target_lang_prob
                    })
                temp_outputs.append(temp)
            outputs = []
            for temp_output in temp_outputs:
                length = len(temp_output[0]["generated_translation"])
                for i in range(length):
                    temp = []
                    for trans in temp_output:
                        temp.append({
                            "target_language": trans["target_language"],
                            "generated_translation": trans['generated_translation'][i],
                            "target_language_probability": trans["target_language_probability"]
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
        }
        model_class = model_mapping.get(model_type)

        if model_class:
            return model_class(modelname, selected_gpu, **kwargs)
        else:
            raise ValueError(f"Unsupported model type: {model_type}")