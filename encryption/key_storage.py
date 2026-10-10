# encryption/key_storage.py
from typing import Dict, List, Optional

class KeyStorage:
    """Хранилище ключей для сессии"""
    
    def __init__(self):
        self._aes_keys: Dict[str, bytes] = {}
        self._time_salts: Dict[str, str] = {}
        self._num_keys: List[str] = []
    
    # AES ключи
    def add_aes_key(self, name: str, key_bytes: bytes) -> None:
        self._aes_keys[name] = key_bytes
    
    def get_aes_key(self, name: str) -> Optional[bytes]:
        return self._aes_keys.get(name)
    
    def get_all_aes_keys(self) -> Dict[str, bytes]:
        return self._aes_keys.copy()
    
    def delete_aes_key(self, name: str) -> bool:
        if name in self._aes_keys:
            del self._aes_keys[name]
            return True
        return False
    
    # Time соли
    def add_time_salt(self, name: str, salt: str) -> None:
        self._time_salts[name] = salt
    
    def get_time_salt(self, name: str) -> Optional[str]:
        return self._time_salts.get(name)
    
    def get_all_time_salts(self) -> Dict[str, str]:
        return self._time_salts.copy()
    
    def delete_time_salt(self, name: str) -> bool:
        if name in self._time_salts:
            del self._time_salts[name]
            return True
        return False
    
    # Номерные ключи
    def add_num_key(self, key: str) -> None:
        if key and key not in self._num_keys:
            self._num_keys.append(key)
    
    def get_all_num_keys(self) -> List[str]:
        return self._num_keys.copy()
    
    def delete_num_key(self, index: int) -> bool:
        if 0 <= index < len(self._num_keys):
            self._num_keys.pop(index)
            return True
        return False
    
    # Очистка
    def clear(self) -> None:
        self._aes_keys.clear()
        self._time_salts.clear()
        self._num_keys.clear()