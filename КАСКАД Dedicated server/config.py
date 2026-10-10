# config.py
import os

class ServerConfig:
    APP_NAME = "EAPM Сервер"
    VERSION = "1.0"
    
    # Настройки сети
    DEFAULT_HOST = "0.0.0.0"      # слушать все интерфейсы
    DEFAULT_PORT = 8888
    
    # Настройки производительности
    MAX_WORKERS = 50              # потоков в пуле
    SOCKET_BACKLOG = 100         # размер очереди подключений
    SOCKET_TIMEOUT = 300         # таймаут на чтение (секунд)
    
    # База данных
    DB_PATH = "mail_server.db"
    DB_POOL_SIZE = 10             # пул соединений SQLite
    
    # Логирование
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
    
    # Пути
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))