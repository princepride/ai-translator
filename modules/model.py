from transformers import MBartForConditionalGeneration, MBart50TokenizerFast
from abc import ABC, abstractmethod
from typing import Type
import torch

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

class MBartModel(Model):
    def __init__(self, modelname, selected_gpu):
        if selected_gpu != "cpu":
            torch.cuda.set_device(selected_gpu)
        self.selected_gpu = selected_gpu
        self.model = MBartForConditionalGeneration.from_pretrained(modelname).to(self.selected_gpu)
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
    
    def generate(self, input, original_language, target_languages):
        assert original_language == "English"
        input_ids = self.tokenizer(input, return_tensors="pt").to(self.selected_gpu)
        output = []
        for target_language in target_languages:
            generated_tokens = self.model.generate(
                **input_ids,
                forced_bos_token_id=self.tokenizer.lang_code_to_id[self.language_mapping(target_language)]
            )
            output.append(self.tokenizer.batch_decode(generated_tokens, skip_special_tokens=True))
        return output
    def fine_tune(self, dict, **kwargs) -> bool:
        pass
    def save(self, path, **kwargs) -> bool:
        pass
    
class ModelFactory:
    @staticmethod
    def create_model(model_type, modelname, selected_gpu, **kwargs) -> Type[Model]:
        model_mapping = {
            "mbart": MBartModel,
        }
        model_class = model_mapping.get(model_type)

        if model_class:
            return model_class(modelname, selected_gpu, **kwargs)
        else:
            raise ValueError(f"Unsupported model type: {model_type}")