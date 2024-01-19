

---
lang: en
---
[English](README.md) | [中文](README_CN.md)

## AI_Translator Instructions

## Install NVIDIA Toolkit

[https://developer.nvidia.com/cuda-downloads](https://developer.nvidia.com/cuda-downloads)

## Install pytorch with gpu version

```
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## Install the other package from requirements

```
pip3 install -r requirements.txt
```

### **Install the models from huggingface**

Navigate to the specific folder to download model, run the following code:

```
git lfs install
git clone git@hf.co:
```

### **Launch:**

In the terminal of your python project platform such as: pycharm, Vscode...

Enjoy the AI-Translator using the command:

``launch.py``
