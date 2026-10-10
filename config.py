# config.py
import os

class Config:
    """Глобальная конфигурация приложения"""
    APP_NAME = "EAPM - КАСКАД"
    VERSION = "2.0"
    
    # Настройки сервера по умолчанию
    DEFAULT_SERVER_DIR = "server"
    
    # Цветовая схема
    THEME = {
        "btn_color": ("#707070", "#505050"),
        "btn_hover": ("#808080", "#606060"),
        "btn_delete": ("#c0392b", "#e74c3c"),
        "card_bg": ("#ffffff", "#2a2a2e"),
        "card_border": ("#cccccc", "#3a3a4e"),
        "text_primary": ("#333333", "#cccccc"),
        "text_secondary": ("#555555", "#aaaaaa"),
    }
    
    # Настройки автообновления
    AUTO_REFRESH_INTERVALS = ["15", "30", "60", "120"]
    DEFAULT_AUTO_REFRESH_INTERVAL = 30
    
    # Настройки шифрования
    AES_KEY_SIZE = 32
    TIME_BUCKET_FORMAT = "%Y-%m-%d %H:%M"
    
    # Пути
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))