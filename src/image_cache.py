from PyQt5 import QtGui

class ImageCache:
    """Global image cache to prevent duplicate loading"""
    _cache = {}
    
    @classmethod
    def get_pixmap(cls, path):
        """Get a pixmap from cache or load it"""
        if path not in cls._cache:
            pixmap = QtGui.QPixmap(path)
            cls._cache[path] = pixmap
        return cls._cache[path]
    
    @classmethod
    def clear(cls):
        """Clear cache to free memory"""
        cls._cache.clear()