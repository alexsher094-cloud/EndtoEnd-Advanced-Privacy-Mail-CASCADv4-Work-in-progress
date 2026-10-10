# server/server_api.py
import os
import shutil
import secrets
import datetime
import time
from typing import List, Tuple, Optional

from models.message import Message
from encryption.aes_cipher import AESCipher
from encryption.time_cipher import TimeCipher
from .user_manager import UserManager

class ServerAPI:
    """API сервера для работы с почтой"""
    
    def __init__(self, base_dir: str = "server"):
        self.base_dir = base_dir
        self.users_file = os.path.join(base_dir, "users.json")
        self.mailboxes_dir = os.path.join(base_dir, "mailboxes")
        
        self.user_manager = UserManager(self.users_file)
        self._init_server()
    
    def _init_server(self) -> None:
        """Инициализация структуры сервера"""
        os.makedirs(self.mailboxes_dir, exist_ok=True)
    
    def _get_user_mailbox(self, login: str) -> str:
        """Получение пути к почтовому ящику пользователя"""
        return os.path.join(self.mailboxes_dir, login)
    
    def _save_message(self, login: str, filename: str, content: str) -> None:
        """Сохранение сообщения в почтовый ящик"""
        mailbox = self._get_user_mailbox(login)
        os.makedirs(mailbox, exist_ok=True)
        
        filepath = os.path.join(mailbox, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        # Для зашифрованных писем устанавливаем старую дату создания
        if "[ENCRYPTED" in content:
            fake_time = time.mktime(datetime.datetime(2020, 1, 1).timetuple())
            os.utime(filepath, (fake_time, fake_time))
    
    def user_exists(self, login: str) -> bool:
        """Проверка существования пользователя"""
        return self.user_manager.user_exists(login)
    
    def register_user(self, login: str, password: str) -> Tuple[bool, str]:
        """Регистрация пользователя"""
        success, msg = self.user_manager.register(login, password)
        if success:
            # Создаём почтовый ящик
            os.makedirs(self._get_user_mailbox(login), exist_ok=True)
            # Отправляем приветственное письмо
            self._send_welcome_message(login)
        return success, msg
    
    def _send_welcome_message(self, login: str) -> None:
        """Отправка приветственного письма"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        welcome = f"От: system\nКому: {login}\nДата: {now}\n\nТема: Добро пожаловать\n\nДобро пожаловать! Это ваше первое письмо."
        self._save_message(login, "welcome.txt", welcome)
    
    def authenticate(self, login: str, password: str) -> Tuple[bool, str]:
        """Аутентификация"""
        return self.user_manager.authenticate(login, password)
    
    def send_message(
        self,
        sender: str,
        recipient: str,
        subject: str,
        body: str,
        encryption_mode: Optional[str] = None,
        aes_key: Optional[bytes] = None,
        time_salt: Optional[str] = None,
        time_bucket: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Отправка сообщения"""
        if not self.user_exists(recipient):
            return False, f"Пользователь '{recipient}' не существует"
        
        plain_body = body
        encrypted_flag = False
        
        if encryption_mode == "aes" and aes_key:
            plain_body = f"[ENCRYPTED_AES]{AESCipher.encrypt(aes_key, body)}"
            encrypted_flag = True
        elif encryption_mode == "time" and time_salt and time_bucket:
            plain_body = f"[ENCRYPTED_TIME]{TimeCipher.encrypt(body, time_salt, time_bucket)}"
            encrypted_flag = True
        
        if encrypted_flag:
            content = f"От: {sender}\nКому: {recipient}\n\nТема: {subject}\n\n{plain_body}"
        else:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            content = f"От: {sender}\nКому: {recipient}\nДата: {now}\n\nТема: {subject}\n\n{plain_body}"
        
        safe_sender = sender.replace(" ", "_")
        safe_recipient = recipient.replace(" ", "_")
        
        if encrypted_flag:
            suffix = secrets.token_hex(16)
            in_filename = f"from_{safe_sender}_{safe_recipient}_{suffix}.txt"
            out_filename = f"to_{safe_recipient}_{safe_sender}_{suffix}.txt"
        else:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            in_filename = f"from_{safe_sender}_{safe_recipient}_{ts}.txt"
            out_filename = f"to_{safe_recipient}_{safe_sender}_{ts}.txt"
        
        self._save_message(recipient, in_filename, content)
        self._save_message(sender, out_filename, content)
        
        return True, "Письмо отправлено"
    
    def get_messages_list(self, login: str) -> List[Message]:
        """Получение списка сообщений"""
        mailbox = self._get_user_mailbox(login)
        if not os.path.exists(mailbox):
            return []
        
        files = [f for f in os.listdir(mailbox) if f.endswith(".txt")]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(mailbox, x)), reverse=True)
        
        messages = []
        for filename in files:
            msg = self._parse_message_file(mailbox, filename)
            if msg:
                messages.append(msg)
        
        return messages
    
    def _parse_message_file(self, mailbox: str, filename: str) -> Optional[Message]:
        """Парсинг файла сообщения"""
        filepath = os.path.join(mailbox, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return None
        
        # Парсинг полей
        sender = "неизвестно"
        recipient = "неизвестно"
        subject = "без темы"
        body_raw = ""
        date_value = None
        
        lines = content.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("От:"):
                sender = line[3:].strip()
            elif line.startswith("Кому:"):
                recipient = line[4:].strip()
            elif line.startswith("Дата:"):
                date_value = line[5:].strip()
            elif line.startswith("Тема:"):
                subject = line[5:].strip()
                i += 1
                while i < len(lines) and lines[i].strip() == "":
                    i += 1
                body_raw = "\n".join(lines[i:]).strip()
                break
            i += 1
        
        is_encrypted = body_raw.startswith("[ENCRYPTED_AES]") or body_raw.startswith("[ENCRYPTED_TIME]")
        display_date = date_value if date_value and not is_encrypted else "скрыто"
        
        return Message(
            filename=filename,
            sender=sender,
            recipient=recipient,
            subject=subject,
            body_raw=body_raw,
            date=display_date,
            is_encrypted=is_encrypted
        )
    
    def decrypt_message_body(self, message: Message, **kwargs) -> str:
        """Расшифрование тела сообщения"""
        enc_type = message.encryption_type
        payload = message.get_encrypted_payload()
        
        if enc_type == "aes":
            aes_key = kwargs.get('aes_key')
            if not aes_key:
                raise ValueError("Нужен ключ AES")
            return AESCipher.decrypt(aes_key, payload)
        elif enc_type == "time":
            time_salt = kwargs.get('time_salt')
            time_bucket = kwargs.get('time_bucket')
            if not time_salt or not time_bucket:
                raise ValueError("Нужны соль и временной интервал")
            return TimeCipher.decrypt(payload, time_salt, time_bucket)
        
        return message.body_raw
    
    def delete_all_messages(self, login: str) -> bool:
        """Удаление всех сообщений пользователя"""
        mailbox = self._get_user_mailbox(login)
        if not os.path.exists(mailbox):
            return False
        
        deleted = 0
        for f in os.listdir(mailbox):
            if f.endswith(".txt"):
                try:
                    os.remove(os.path.join(mailbox, f))
                    deleted += 1
                except Exception:
                    pass
        return deleted > 0
    
    def delete_user(self, login: str) -> bool:
        """Полное удаление пользователя"""
        success = self.user_manager.delete_user(login)
        if success:
            mailbox = self._get_user_mailbox(login)
            if os.path.exists(mailbox):
                shutil.rmtree(mailbox)
        return success