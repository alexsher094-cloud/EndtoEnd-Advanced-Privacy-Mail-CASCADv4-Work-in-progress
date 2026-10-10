# cert_utils.py
import os
import ipaddress
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

def generate_self_signed_cert(cert_path="server.crt", key_path="server.key", 
                              common_name="localhost", days_valid=365,
                              force_regen=False):
    """
    Генерирует самоподписанный сертификат с поддержкой IPv4 и IPv6.
    """
    if not force_regen and os.path.exists(cert_path) and os.path.exists(key_path):
        return cert_path, key_path

    # Генерация ключа
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Формирование имени субъекта
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "RU"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Moscow"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Moscow"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "EAPM"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    # --- Исправление: Правильное создание SAN с поддержкой IPv6 ---
    # Начинаем список alt_names с DNS-имени, что является стандартом.
    alt_names = [x509.DNSName(common_name), x509.DNSName("localhost")]

    # Добавляем IP-адреса, корректно обрабатывая IPv4 и IPv6.
    # Список адресов, которые будут добавлены в SAN.
    ip_addresses_to_add = ["127.0.0.1", "::1"]
    for ip_str in ip_addresses_to_add:
        try:
            # Пытаемся преобразовать строку в объект IP-адреса с помощью ipaddress.ip_address()
            # Эта функция автоматически определит тип (IPv4 или IPv6).
            ip_obj = ipaddress.ip_address(ip_str)
            alt_names.append(x509.IPAddress(ip_obj))
        except ValueError:
            # Логируем ошибку, если строка не является корректным IP-адресом.
            print(f"Предупреждение: Не удалось распознать IP-адрес '{ip_str}'")

    # Создаём расширение Subject Alternative Name (SAN) с нашим списком.
    san = x509.SubjectAlternativeName(alt_names)
    # --- Конец исправления ---

    # Создание сертификата
    cert = (x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=days_valid))
            .add_extension(san, critical=False)  # <-- Добавляем исправленное расширение SAN
            # .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True) # Можно раскомментировать для BasicConstraints
            .sign(private_key, hashes.SHA256()))

    # Сохранение ключа и сертификата
    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    return cert_path, key_path