import logging
import sys
import warnings
from modules.timer import startup_timer

def imports():
    logging.getLogger("torch.distributed.nn").setLevel(logging.ERROR)  # sshh...
    logging.getLogger("xformers").addFilter(lambda record: 'A matching Triton is not available' not in record.getMessage())

    import torch  # noqa: F401
    startup_timer.record("import torch")
    warnings.filterwarnings(action="ignore", category=DeprecationWarning, module="pytorch_lightning")
    warnings.filterwarnings(action="ignore", category=UserWarning, module="torchvision")

    import gradio
    startup_timer.record("import gradio")

    # from modules import paths, timer, import_hook, errors  # noqa: F401
    # startup_timer.record("setup paths")

    # from modules import shared_init
    # shared_init.initialize()
    # startup_timer.record("initialize shared")

    # from modules import processing, gradio_extensons, ui  # noqa: F401
    # startup_timer.record("other imports")