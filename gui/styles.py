# gui/styles.py
from config import Config

class Styles:
    """Централизованное управление стилями"""
    
    # Основные цвета
    BTN_COLOR = Config.THEME["btn_color"]
    BTN_HOVER = Config.THEME["btn_hover"]
    BTN_DELETE = Config.THEME["btn_delete"]
    CARD_BG = Config.THEME["card_bg"]
    CARD_BORDER = Config.THEME["card_border"]
    TEXT_PRIMARY = Config.THEME["text_primary"]
    TEXT_SECONDARY = Config.THEME["text_secondary"]
    
    # Шрифты
    FONT_TITLE = ("Segoe UI", 18, "bold")
    FONT_HEADER = ("Segoe UI", 14, "bold")
    FONT_NORMAL = ("Segoe UI", 12)
    FONT_SMALL = ("Segoe UI", 11)
    FONT_BOLD = ("Segoe UI", 13, "bold")
    FONT_MONO = ("Consolas", 12)
    
    @classmethod
    def configure_ctk(cls):
        """Настройка customtkinter"""
        import customtkinter as ctk
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")