import os
import pathlib
from loguru import logger
from graia.saya import Channel, Saya

channel = Channel.current()
saya = Saya.current()

# 定义文件夹所在的路径
folder_path = os.path.dirname(__file__)


def import_modules(path, current_package):
    for name in [f.name for f in pathlib.Path(path).iterdir() if f.name.endswith(".py") and not f.is_dir()]:
        if name.startswith("_"):
            continue
        module_name = f"{current_package}.{name[:-3]}"
        try:
            with saya.module_context():
                saya.require(module_name)
        except Exception as e:
            logger.error(f"{module_name}导入失败\n{e}")
        else:
            logger.success(f"{module_name}导入成功")
    # 递归一层深度导入子文件夹
    folder_names = [f.name for f in pathlib.Path(path).iterdir() if f.is_dir()]
    for sub_name in folder_names:
        if sub_name.startswith("_"):
            continue
        import_modules(os.path.join(path, sub_name), f"{current_package}.{sub_name}")


import_modules(folder_path, __package__)
