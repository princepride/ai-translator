import os

def path_parsing(path, suffix):
    """
    返回指定路径下满足后缀的文件路径列表

    Args:
    - path (str): 目标路径
    - suffix (str): 后缀

    Returns:
    - List[str]: 满足后缀的文件路径列表
    """
    result = []

    # 遍历指定路径下的所有文件和文件夹
    for root, dirs, files in os.walk(path):
        for file in files:
            # 判断文件后缀是否匹配
            if file.endswith(suffix):
                result.append(os.path.join(root, file))

    return result

def get_folders(path, model_type):
    """
    返回指定路径下的文件夹列表

    Args:
    - path (str): 目标路径，可以是相对路径或绝对路径
    - model_type (str): 模型类型

    Returns:
    - List[dict]: 包含模型类型和文件夹绝对路径的字典列表
    """
    result = []
    # 确保路径是绝对路径
    abs_path = os.path.abspath(path)

    # 遍历指定路径下的所有文件和文件夹
    for root, dirs, files in os.walk(abs_path):
        # 只添加文件夹到结果列表中
        for folder in dirs:
            result.append({"model_type": model_type, "path": os.path.join(root, folder)})

        # 避免进入子文件夹，只需要处理当前层级的文件夹
        break

    return result

def path_filename_extra(paths, include_suffix=False):
    """
    返回文件路径列表中的文件名列表

    Args:
    - paths (List[str]): 文件路径列表
    - include_suffix (bool): 是否包含文件后缀，默认为 False

    Returns:
    - Dict[str]: 文件名列表
    """
    filenames = {}

    for path in paths:
        # 使用 os.path.basename 获取文件名
        filename = os.path.basename(path)

        # 根据 include_suffix 参数决定是否保留文件后缀
        if not include_suffix:
            filename, _ = os.path.splitext(filename)

        filenames[filename] = path

    return filenames

def path_foldername_mapping(paths):
    """
    返回文件路径列表中的文件夹名到文件夹路径的映射字典

    Args:
    - paths (List[str]): 文件路径列表

    Returns:
    - Dict[str]: 文件夹名到文件夹路径的映射字典
    """
    folder_mapping = {}
    for path in paths:
        # 使用 os.path.basename 获取文件夹名
        folder_name = os.path.basename(path["path"])
        folder_mapping[folder_name] = {"path":path["path"], "model_type":path["model_type"]}
    return folder_mapping