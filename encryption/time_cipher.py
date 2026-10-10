# encryption/time_cipher.py
import hashlib
from .aes_cipher import AESCipher

class TimeCipher:
    """Time-based шифрование"""
    
    @staticmethod
    def encrypt(plaintext: str, salt: str, time_bucket: str) -> str:
        """Шифрование с привязкой к временному интервалу"""
        key = hashlib.sha256((time_bucket + salt).encode()).digest()
        return AESCipher.encrypt(key, plaintext)
    
    @staticmethod
    def decrypt(encrypted_b64: str, salt: str, time_bucket: str) -> str:
        """Расшифрование с привязкой к временному интервалу"""
        key = hashlib.sha256((time_bucket + salt).encode()).digest()
        return AESCipher.decrypt(key, encrypted_b64)