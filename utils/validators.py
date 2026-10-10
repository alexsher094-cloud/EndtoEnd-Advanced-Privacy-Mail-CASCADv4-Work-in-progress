# utils/validators.py
import base64
from typing import Tuple, Optional

class Validators:
    """Валидаторы для различных типов данных"""
    
    @staticmethod
    def validate_aes_key(key_str: str) -> Tuple[bool, Optional[bytes], str]:
        """Валидация AES ключа (32 байта в base64 или hex)"""
        if not key_str:
            return False, None, "Ключ не может быть пустым"
        
        # Попытка декодировать как base64
        try:
            key_bytes = base64.b64decode(key_str)
            if len(key_bytes) == 32:
                return True, key_bytes, "OK"
        except Exception:
            pass
        
        # Попытка декодировать как hex
        try:
            key_bytes = bytes.fromhex(key_str)
            if len(key_bytes) == 32:
                return True, key_bytes, "OK"
        except Exception:
            pass
        
        return False, None, "Ключ должен быть 32 байта в base64 или hex"
    
    @staticmethod
    def validate_time_salt(salt: str) -> Tuple[bool, str]:
        """Валидация соли для time-based шифрования"""
        if not salt:
            return False, "Соль не может быть пустой"
        if len(salt) < 6:
            return False, "Соль должна быть не менее 6 символов"
        if len(salt) > 256:
            return False, "Соль должна быть не более 256 символов"
        return True, "OK"
    
    @staticmethod
    def validate_login(login: str) -> Tuple[bool, str]:
        """Валидация логина"""
        if not login:
            return False, "Логин не может быть пустым"
        if len(login) < 3:
            return False, "Логин должен быть не менее 3 символов"
        if len(login) > 50:
            return False, "Логин должен быть не более 50 символов"
        # Разрешены буквы, цифры, underscore, дефис
        import re
        if not re.match(r'^[a-zA-Zа-яА-ЯёЁ0-9_-]+$', login):
            return False, "Логин может содержать только буквы, цифры, _ и -"
        return True, "OK"
    
    @staticmethod
    def validate_password(password: str) -> Tuple[bool, str]:
        """Валидация пароля"""
        if not password:
            return False, "Пароль не может быть пустым"
        if len(password) < 4:
            return False, "Пароль должен быть не менее 4 символов"
        return True, "OK"