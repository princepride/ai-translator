[English](README.md) | [中文](README_CN.md)

## AI_Translator 安装说明

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

导航至特定文件夹下载模型，运行以下代码：

```
git lfs install
git clone git@hf.co:
```

## **启动：**

在你的 Python 项目平台（如 PyCharm、Vscode...）的终端中，

使用以下命令享受 AI 翻译器：

`launch.py`

# AI_Translator 使用说明

## 第一步：

![1705652320228](image/README_CN/1705652320228.png)

## 第二步：

![1705653144370](image/README_CN/1705653144370.png)

## 第三步：

![1705653166073](image/README_CN/1705653166073.png)
