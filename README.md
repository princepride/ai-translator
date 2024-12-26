# AI_Translator 安装说明

## 安装 NVIDIA Driver

[NVIDIA 驱动下载链接](https://www.nvidia.com/download/index.aspx)

安装完成后，运行以下指令看是否安装成功：

```
nvidia-smi
```

### 安装 NVIDIA Toolkit

[NVIDIA Toolkit 下载链接](https://developer.nvidia.com/cuda-downloads)

安装完成后，运行以下指令看是否安装成功：

```
nvcc --version
```

### 安装支持 GPU 的 PyTorch 版本

```
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 从 requirements 安装其他包

```
pip3 install -r requirements.txt
```

## **从 huggingface 安装模型**

导航至 `/src/models/local` 文件夹下载模型，运行以下代码：

```
git lfs install
```

### 安装 nllb-200-distilled-1.3B 模型

```
git clone https://princepride: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@huggingface.co/yonyou-sg/nllb-200-distilled-1.3B
```

### 安装 Qwen2.5-7B-Instruct 模型

```
git clone https://princepride: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@huggingface.co/yonyou-sg/Qwen2.5-7B-Instruct
```

### 安装 Qwen2-7B-Instruct-Full-Finetune  模型

```
git clone https://princepride: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@huggingface.co/yonyou-sg/Qwen2-7B-Instruct-Full-Finetune 
```

## **启动：**

在你的 Python 项目平台（如 PyCharm、Vscode...）的终端中，

使用以下命令享受 AI 翻译器：

`fastapi dev launch.py`

# AI_Translator 使用说明

## 第一步：

![1705652320228](image/README_CN/1705652320228.png)

## 第二步：

![1705653144370](image/README_CN/1705653144370.png)

## 第三步：

![1705653166073](image/README_CN/1705653166073.png)

应用提供了Excel批量翻译功能和markdown批量翻译功能，如果Excel格式类似，可以通过指定翻译列和写入列，批量翻译Excel

![1731035178327](image/README/1731035178327.png)

## 一键部署

把文件：`./deploy/ai_translator.ipynb 放到Google drive里，双击用Colab打开，点击一键部署即可`
