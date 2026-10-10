# server/user_manager.py
import os
import json
import hashlib
from typing import Tuple, Dict

class UserManager:
    """Управление пользователями сервера"""
    
    def __init__(self, users_file: str):
        self.users_file = users_file
        self._init_users_file()
    
    def _init_users_file(self) -> None:
        """Инициализация файла пользователей"""
        if not os.path.exists(self.users_file):
            with open(self.users_file, "w", encoding="utf-8") as f:
                json.dump({}, f)
    
    def _load_users(self) -> Dict:
        """Загрузка пользователей из файла"""
        with open(self.users_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _save_users(self, users: Dict) -> None:
        """Сохранение пользователей в файл"""
        with open(self.users_file, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4)
    
    @staticmethod
    def _hash_password(password: str) -> str:
        """Хеширование пароля с солью"""
        salt = os.urandom(32)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        return salt.hex() + ':' + pwd_hash.hex()
    
    @staticmethod
    def _verify_password(stored: str, provided: str) -> bool:
        """Проверка пароля"""
        try:
            salt_hex, hash_hex = stored.split(':')
            salt = bytes.fromhex(salt_hex)
            pwd_hash = hashlib.pbkdf2_hmac('sha256', provided.encode(), salt, 100000)
            return pwd_hash.hex() == hash_hex
        except Exception:
            return False
    
    def user_exists(self, login: str) -> bool:
        """Проверка существования пользователя"""
        return login in self._load_users()
    
    def register(self, login: str, password: str) -> Tuple[bool, str]:
        """Регистрация нового пользователя"""
        users = self._load_users()
        if login in users:
            return False, "Пользователь уже существует"
        
        users[login] = self._hash_password(password)
        self._save_users(users)
        return True, "Регистрация успешна"
    
    def authenticate(self, login: str, password: str) -> Tuple[bool, str]:
        """Аутентификация пользователя"""
        users = self._load_users()
        if login not in users:
            return False, "Логин не найден"
        
        stored = users[login]
        # Поддержка старого формата (без хеширования)
        if ':' not in stored:
            if stored == password:
                users[login] = self._hash_password(password)
                self._save_users(users)
                return True, "OK"
            return False, "Неверный пароль"
        
        if self._verify_password(stored, password):
            return True, "OK"
        return False, "Неверный пароль"
    
    def delete_user(self, login: str) -> bool:
        """Удаление пользователя"""
        users = self._load_users()
        if login not in users:
            return False
        del users[login]
        self._save_users(users)
        return True