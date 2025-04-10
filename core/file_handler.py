# core/file_handler.py
import os

SUPPORTED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}

def get_image_files(folder_path: str, recursive: bool = False) -> list[str]:
    """
    查找指定文件夹中的图像文件。
    Args:
        folder_path: 文件夹的路径。
        recursive: 是否搜索子文件夹。
    Returns:
        图像文件的绝对路径列表。
    """
    image_files = []
    if not os.path.isdir(folder_path):
        return image_files

    if recursive:
        for root, _, files in os.walk(folder_path):
            for filename in files:
                if os.path.splitext(filename)[1].lower() in SUPPORTED_EXTENSIONS:
                    image_files.append(os.path.join(root, filename))
    else:
        try:
            for filename in os.listdir(folder_path):
                if os.path.splitext(filename)[1].lower() in SUPPORTED_EXTENSIONS:
                    full_path = os.path.join(folder_path, filename)
                    if os.path.isfile(full_path): # 确保它是一个文件
                        image_files.append(full_path)
        except OSError as e:
            print(f"Error listing directory {folder_path}: {e}")


    return sorted(image_files) # 排序以获得一致的顺序
