import torch
def get_gpu_info():
    print(torch.__version__)
    gpu_info = ["cpu"]
    try:
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_info.extend([torch.cuda.get_device_name(i) for i in range(gpu_count)])
    except Exception as e:
        pass
    return gpu_info