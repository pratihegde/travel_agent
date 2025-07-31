import logging
import sys
from typing import Optional

def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """Get configured logger instance"""
    
    # Determine log level
    if level is None:
        from .config import Config
        level = "DEBUG" if Config.DEBUG else "INFO"
    
    # Create logger
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if not logger.handlers:
        # Create handler
        handler = logging.StreamHandler(sys.stdout)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, level.upper()))
    
    return logger