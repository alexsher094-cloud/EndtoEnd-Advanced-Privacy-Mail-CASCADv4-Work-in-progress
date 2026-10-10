# hybrid_steganography.py
import os
import struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# ------------------------------------------------------------
# AES-ключ (256 бит)
# ------------------------------------------------------------
def generate_aes_key() -> bytes:
    """Генерирует случайный AES-256 ключ (32 байта)."""
    return os.urandom(32)

def save_aes_key(key: bytes, filename: str) -> None:
    with open(filename, 'wb') as f:
        f.write(key)

def load_aes_key(filename: str) -> bytes:
    with open(filename, 'rb') as f:
        return f.read()

# ------------------------------------------------------------
# Шифрование AES-GCM с помощью cryptography
# ------------------------------------------------------------
def aes_gcm_encrypt(key: bytes, plaintext: bytes) -> bytes:
    """Возвращает iv (12 байт) + ciphertext + tag (16 байт)."""
    iv = os.urandom(12)
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(plaintext) + encryptor.finalize()
    return iv + ciphertext + encryptor.tag

def aes_gcm_decrypt(key: bytes, iv_ciphertext_tag: bytes) -> bytes:
    """Извлекает iv (12), ciphertext, tag (16) и расшифровывает."""
    if len(iv_ciphertext_tag) < 12 + 16:
        raise ValueError("Данные слишком короткие")
    iv = iv_ciphertext_tag[:12]
    tag = iv_ciphertext_tag[-16:]
    ciphertext = iv_ciphertext_tag[12:-16]
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend())
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    return plaintext

# ------------------------------------------------------------
# Основные операции: шифрование + генерация ключа-файла
# ------------------------------------------------------------
def encrypt_and_make_key(message: str, carrier: str, aes_key: bytes) -> bytes:
    """
    Шифрует сообщение AES-256-GCM, затем комбинирует с посылкой через XOR.
    Возвращает ключ-файл.
    """
    msg_bytes = message.encode('utf-8')
    total_cipher = aes_gcm_encrypt(aes_key, msg_bytes)   # iv (12) + ciphertext + tag (16)

    carrier_bytes = carrier.encode('utf-8')
    len_total = len(total_cipher)
    max_len = max(len_total, len(carrier_bytes))

    total_padded = total_cipher + b'\x00' * (max_len - len_total)
    carrier_padded = carrier_bytes + b'\x00' * (max_len - len(carrier_bytes))

    key_bytes = bytearray()
    key_bytes.extend(len_total.to_bytes(4, 'little'))
    for i in range(max_len):
        key_bytes.append(total_padded[i] ^ carrier_padded[i])
    return bytes(key_bytes)

def recover_from_key(key_bytes: bytes, carrier: str, aes_key: bytes) -> str:
    """Восстанавливает сообщение из ключа-файла, посылки и AES-ключа."""
    if len(key_bytes) < 4:
        raise ValueError("Ключ-файл слишком короткий")
    len_total = struct.unpack('<I', key_bytes[:4])[0]
    key_data = key_bytes[4:]

    carrier_bytes = carrier.encode('utf-8')
    max_len = len(key_data)
    carrier_padded = carrier_bytes + b'\x00' * (max_len - len(carrier_bytes))

    total_padded = bytearray()
    for i in range(max_len):
        total_padded.append(key_data[i] ^ carrier_padded[i])
    total_cipher = bytes(total_padded[:len_total])

    plaintext = aes_gcm_decrypt(aes_key, total_cipher)
    return plaintext.decode('utf-8')

def save_keyfile(keyfile_bytes: bytes, filename: str) -> None:
    with open(filename, 'wb') as f:
        f.write(keyfile_bytes)

def load_keyfile(filename: str) -> bytes:
    with open(filename, 'rb') as f:
        return f.read()