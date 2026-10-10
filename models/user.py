# models/user.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    """Модель пользователя"""
    login: str
    password_hash: Optional[str] = None
    is_authenticated: bool = False
    
    def to_dict(self) -> dict:
        """Конвертация в словарь для JSON"""
        return {
            "login": self.login,
            "password_hash": self.password_hash
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        """Создание из словаря"""
        return cls(
            login=data.get("login", ""),
            password_hash=data.get("password_hash")
        )