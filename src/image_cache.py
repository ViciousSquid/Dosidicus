from PyQt5 import QtGui

class ImageCache:
    """Global image cache to prevent duplicate loading"""
    _cache = {}
    
    @classmethod
# from typing import Dict
from PyQt5.QtGui import QPixmap

def get_pixmap(cls, path: str) -> QPixmap:
    """Get a pixmap from cache or load it"""
    if path not in cls._cache:
        pixmap = QtGui.QPixmap(path)
        cls._cache[path] = pixmap
    return cls._cache[path]
    
    @classmethod
# from typing import Type

def clear(cls: type) -> None:
    """Clear cache to free memory"""
    cls._cache.clear()