import logging
import os
from datetime import datetime

def get_logger(name: str) -> logging.Logger:
    """
    Creates a logger that writes to both:
    - the console (so you see it live)
    - a log file in logs/ (so you keep history)
    """
    # Create logs folder if it doesn't exist
    os.makedirs('logs', exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Avoid adding duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        '%(asctime)s — %(levelname)s — %(name)s — %(message)s'
    )

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler
    log_filename = f"logs/etl_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger