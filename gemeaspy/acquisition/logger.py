import os
import logging
from pathlib import Path

def setup_logger(log_path: str) -> logging.Logger:
    global logger
    logging.getLogger("paramiko").setLevel(logging.ERROR)
    os.makedirs(Path(log_path).parent, exist_ok=True)
    logger = logging.Logger("acquisition")
    logger.addHandler(logging.FileHandler(log_path))
    return logger

logger: logging.Logger = setup_logger("log/acquisition.log")