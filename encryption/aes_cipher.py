# encryption/aes_cipher.py
import base64
import secrets
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

class AESCipher:
    """AES-256 шифрование"""
    
    @staticmethod
    def encrypt(key: bytes, plaintext: str) -> str:
        """Шифрование текста AES-256 в режиме CBC"""
        iv = secrets.token_bytes(16)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        
        data = plaintext.encode('utf-8')
        pad_len = 16 - (len(data) % 16) or 16
        padded = data + bytes([pad_len]) * pad_len
        
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(iv + ciphertext).decode('utf-8')
    
    @staticmethod
    def decrypt(key: bytes, encrypted_b64: str) -> str:
        """Расшифрование текста"""
        data = base64.b64decode(encrypted_b64)
        iv, ciphertext = data[:16], data[16:]
        
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_padded = decryptor.update(ciphertext) + decryptor.finalize()
        
        pad_len = decrypted_padded[-1]
        if pad_len < 1 or pad_len > 16:
            raise ValueError("Invalid padding")
        
        return decrypted_padded[:-pad_len].decode('utf-8')
    
    @staticmethod
    def generate_key() -> bytes:
        """Генерация случайного AES-ключа (32 байта)"""
        return secrets.token_bytes(32)