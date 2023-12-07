from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, GenerationConfig, TrainingArguments, Trainer
import torch
from peft import PeftModel, PeftConfig
import yaml

with open("config.yml", "r") as yaml_file:
    config = yaml.safe_load(yaml_file)

def generate_translate_prompts(original_language, target_language, prompts):
    return f"translate from {original_language} to {target_language}, {prompts}"
class T5Processor:
    def __init__(self, model_name, device) -> None:
        self.model_name = model_name
        self.original_model = AutoModelForSeq2SeqLM.from_pretrained(model_name, torch_dtype=torch.bfloat16)
        self.tokenier = AutoTokenizer.from_pretrained(model_name)
        self.device = device
        try:
            self.original_model = AutoModelForSeq2SeqLM.from_pretrained(model_name, torch_dtype=torch.bfloat16)
        except:
            print("T5 model load error")
        try:
            self.tokenier = AutoTokenizer.from_pretrained(model_name)
        except:
            print("tokenier load error")

    def __init__(self, model_name, lora_model_name, device) -> None:
        self.model_name = model_name
        self.lora_model_name = lora_model_name
        self.device = device
        try:
            self.original_model = AutoModelForSeq2SeqLM.from_pretrained(model_name, torch_dtype=torch.bfloat16)
        except:
            print("T5 model load error")
        try:
            self.tokenier = AutoTokenizer.from_pretrained(model_name)
        except:
            print("tokenier load error")
        try:
            self.peft_model = PeftModel.from_pretrained(self.original_model, config["model_path"]["t5_model_path"] + self.lora_model_name, torch_dtype=torch.bfloat16, is_trainable=False)
        except:
            print("The base model and lora model do not match")
    
    def generate(self, original_language, target_language, prompts):
        prompts = generate_translate_prompts(original_language, target_language, prompts)
        input_ids = self.tokenizer(prompts, return_tensors="pt").input_ids
        if self.peft_model:
            model_outputs = self.peft_model.generate(input_ids=input_ids, generation_config=GenerationConfig(max_new_tokens=200, num_beams=1))
        else:                                                                                                                                                         
            model_outputs = self.original_model.generate(input_ids=input_ids, generation_config=GenerationConfig(max_new_tokens=200, num_beams=1))
        model_text_output = self.tokenizer.decode(model_outputs[0], skip_special_tokens=True)
        return model_text_output