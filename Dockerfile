FROM huggingface/transformers-pytorch-gpu
LABEL maintainer="EggcakeXue<e1132271@u.nus.edu>"

# 设置 python 环境变量
ENV PYTHONUNBUFFERED 1

#安装 gradio,peft,PyYAML
RUN pip install --no-cache-dir gradio==4.13.0 \
							   peft==0.7.1 \
							   PyYAML==6.0.1

#安装 openpyxl, torch, transformers
RUN pip install --no-cache-dir openpyxl==3.1.2 \
							   torch==2.0.1+cu118 \
							   transformers==4.36.2

#复制launch.py到容器中的自定义目录（根据需求修改）
COPY launch.py /use/local

CMD echo $MYPATH
CMD echo "Launch --------------successfully!"
#指定容器启动时运行的命令
CMD ["python", "launch.py"]



