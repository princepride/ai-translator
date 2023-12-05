FROM huggingface/transformers-pytorch-gpu

# 安装 gradio
RUN pip install gradio

# 设置工作目录
WORKDIR /app

# 复制 launch.py 到容器中的 /app 目录
COPY launch.py /app/

# 指定容器启动时运行的命令
CMD ["python", "launch.py"]
