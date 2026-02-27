# localisation.py
import json
import os
import sys
from pathlib import Path

class Localisation:
    _instance = None
    
    @classmethod
    def instance(cls):
        """Return the singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """Initialize with default language"""
        self.translations = {}
        self.current_language = 'en'
        self.load_language('en')
    
    def load_language(self, lang_code):
        """Load translations from language module"""
        # Attempt 1: Try import from src.translations (Standard Project Structure)
        try:
            module_name = f'src.translations.{lang_code}'
            module = __import__(module_name, fromlist=['translations'])
            self.translations = getattr(module, 'translations', {})
            self.current_language = lang_code
            print(f"[Localisation] Successfully loaded '{lang_code}' from {module_name}")
            return
        except ImportError:
            pass

        # Attempt 2: Try import from translations (Flat/Root Structure)
        try:
            module_name = f'translations.{lang_code}'
            module = __import__(module_name, fromlist=['translations'])
            self.translations = getattr(module, 'translations', {})
            self.current_language = lang_code
            print(f"[Localisation] Successfully loaded '{lang_code}' from {module_name}")
            return
        except ImportError as e:
            # Fallback: No translations found
            print(f"[Localisation] WARNING: Could not load translations for '{lang_code}'. Error: {e}")
            self.translations = {}
    
    def get(self, key, default=None, **kwargs):
        """
        Get a translation string with optional formatting.
        
        Args:
            key: Translation key to look up
            default: Default value if key not found
            **kwargs: Formatting arguments for the translation string
        
        Returns:
            Translated and formatted string
        """
        if not key:
            return default or ""
        
        # Look up the translation
        value = self.translations.get(key, default)
        
        # If no value found, use the key itself as default
        if value is None:
            value = str(key)
        
        # Format with kwargs if provided
        if kwargs and isinstance(value, str):
            try:
                return value.format(**kwargs)
            except (KeyError, ValueError):
                # Return unformatted string if formatting fails
                return value
        
        return value
    
    def set_language(self, lang_code):
        """Change the current language"""
        self.load_language(lang_code)
    
    def get_available_languages(self):
        """Scan the translations folder and return sorted list of language codes"""
        languages = set()
        
        # Scan root/translations directory
        try:
            # Go up one level from src/ to root/, then into translations/
            root_dir = Path(__file__).parent.parent
            trans_dir = root_dir / "translations"
            
            if trans_dir.exists():
                for file_path in trans_dir.glob("*.py"):
                    lang_code = file_path.stem.lower()
                    if lang_code not in ('__init__',) and not lang_code.startswith('_'):
                        languages.add(lang_code)
        except Exception as e:
            print(f"[Localisation] Error scanning translations directory: {e}")
        
        return sorted(list(languages))

    def get_language_name(self, lang_code, fallback=True):
        """Get the display name for a language code"""
        if not lang_code:
            return "Unknown"
        
        # Try to get native name from translation file
        try:
            original_lang = self.current_language
            self.load_language(lang_code)
            name = self.translations.get('language_name_native') or \
                   self.translations.get('language_name')
            self.load_language(original_lang)
            
            if name:
                return name
        except Exception as e:
            print(f"[Localisation] Error getting name for '{lang_code}': {e}")
        
        # Fallback to hardcoded map
        if fallback:
            fallback_names = {
                'en': 'English', 'es': 'Spanish (Español)', 'fr': 'French (Français)',
                'de': 'German (Deutsch)', 'pl': 'Polish (Polski)', 'uk': 'Ukrainian (Українська)',
                'zh': 'Chinese (中文)', 'ja': 'Japanese (日本語)', 'pt': 'Portuguese (Português)',
                'cy': 'Welsh (Cymraeg)', 'ga': 'Irish (Gaeilge)', 'gen_z': 'Gen Z Slang',
            }
            return fallback_names.get(lang_code, lang_code.upper())
        
        return lang_code
    
    # =====================================================================
    # PERSONALITY TRANSLATION METHODS
    # =====================================================================
    
    def get_personality_name(self, personality):
        """Get translated personality display name."""
        key = personality.value if hasattr(personality, 'value') else str(personality).lower()
        return self.get(f'personality_{key}', key.capitalize())
    
    def get_personality_description(self, personality):
        """Get translated personality description text."""
        key = personality.value if hasattr(personality, 'value') else str(personality).lower()
        return self.get(f'desc_{key}', '')
    
    def get_personality_modifier_text(self, personality):
        """Get translated personality modifier summary."""
        key = personality.value if hasattr(personality, 'value') else str(personality).lower()
        return self.get(f'mod_{key}', 'Balanced')
    
    def get_personality_modifiers(self, personality):
        """Get translated detailed personality modifiers."""
        key = personality.value if hasattr(personality, 'value') else str(personality).lower()
        return self.get(f'modifiers_{key}', '')
    
    def get_care_tips(self, personality):
        """Get translated care tips for personality."""
        key = personality.value if hasattr(personality, 'value') else str(personality).lower()
        return self.get(f'tips_{key}', '')


# Robust alias for direct access to the get method
def loc(key, default=None, **kwargs):
    """Convenient alias for Localisation.instance().get()"""
    return Localisation.instance().get(key, default, **kwargs)

def set_language(lang_code):
    """
    Set the global language for the Localisation singleton.
    Args:
        lang_code: Language code (e.g., 'en', 'zh')
    """
    Localisation.instance().set_language(lang_code)

# Legacy alias for American spelling compatibility
Localization = Localisation