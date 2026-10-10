# storage/local_file_repo.py
import os
import json
import uuid
import shutil
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
from models.message import Message
from server.user_manager import UserManager

class LocalFileRepository:
    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

        self.messages_dir = os.path.join(self.base_dir, "messages")
        self.attachments_dir = os.path.join(self.base_dir, "attachments")
        self.mailboxes_dir = os.path.join(self.base_dir, "mailboxes")
        self.users_file = os.path.join(self.base_dir, "users.json")

        self.user_manager = UserManager(self.users_file)

        os.makedirs(self.messages_dir, exist_ok=True)
        os.makedirs(self.attachments_dir, exist_ok=True)
        os.makedirs(self.mailboxes_dir, exist_ok=True)

    # ========== Вспомогательные методы ==========
    def _get_user_index_path(self, login: str) -> str:
        return os.path.join(self.mailboxes_dir, login, "index.json")

    def _load_user_index(self, login: str) -> Dict:
        path = self._get_user_index_path(login)
        if not os.path.exists(path):
            return {"messages": []}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_user_index(self, login: str, index: Dict):
        user_dir = os.path.join(self.mailboxes_dir, login)
        os.makedirs(user_dir, exist_ok=True)
        with open(self._get_user_index_path(login), "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)

    def _save_message_file(self, msg: Message):
        filepath = os.path.join(self.messages_dir, f"{msg.filename}.json")
        data = {
            "id": msg.filename,
            "sender": msg.sender,
            "recipient": msg.recipient,
            "subject": msg.subject,
            "encryption_type": msg.encryption_type,
            "body": msg.body_raw,
            "stego_key_hex": msg.stego_key_hex,
            "attachments": msg.attachments
        }
        if msg.date is not None:
            data["timestamp"] = msg.date

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_message_file(self, msg_id: str) -> Optional[Message]:
        filepath = os.path.join(self.messages_dir, f"{msg_id}.json")
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Message(
            filename=data["id"],
            sender=data["sender"],
            recipient=data["recipient"],
            subject=data["subject"],
            body_raw=data["body"],
            date=data.get("timestamp"),
            is_encrypted=bool(data.get("encryption_type")),
            encryption_type=data.get("encryption_type"),
            stego_key_hex=data.get("stego_key_hex"),
            attachments=data.get("attachments", [])
        )

    # ========== Пользователи ==========
    def user_exists(self, login: str) -> bool:
        return self.user_manager.user_exists(login)

    def register_user(self, login: str, password: str) -> Tuple[bool, str]:
        success, msg = self.user_manager.register(login, password)
        if success:
            self._save_user_index(login, {"messages": []})
            self._send_welcome_message(login)
        return success, msg

    def authenticate(self, login: str, password: str) -> Tuple[bool, str]:
        return self.user_manager.authenticate(login, password)

    def delete_user(self, login: str) -> bool:
        user_dir = os.path.join(self.mailboxes_dir, login)
        if os.path.exists(user_dir):
            shutil.rmtree(user_dir)
        return self.user_manager.delete_user(login)

    def _send_welcome_message(self, login: str):
        welcome_body = "Добро пожаловать в EAPM КАСКАД!"
        self.send_message(
            sender="system",
            recipient=login,
            subject="Добро пожаловать!",
            body=welcome_body,
            encryption_mode=None
        )

    # ========== Работа с сообщениями ==========
    def send_message(
        self,
        sender: str,
        recipient: str,
        subject: str,
        body: str,
        encryption_mode: Optional[str] = None,
        aes_key: Optional[bytes] = None,
        time_salt: Optional[str] = None,
        time_bucket: Optional[str] = None,
        attachments: Optional[List[Tuple[str, bytes]]] = None
    ) -> Tuple[bool, str]:
        if not self.user_exists(recipient):
            return False, f"Пользователь '{recipient}' не существует"

        # Шифруем тело, если нужно
        final_body = body
        if encryption_mode == "aes" and aes_key:
            from encryption.aes_cipher import AESCipher
            final_body = AESCipher.encrypt(aes_key, body)
        elif encryption_mode == "time" and time_salt and time_bucket:
            from encryption.time_cipher import TimeCipher
            final_body = TimeCipher.encrypt(body, time_salt, time_bucket)

        msg_id = str(uuid.uuid4())
        timestamp = None if encryption_mode else datetime.now().isoformat()

        # Обработка вложений
        attachment_infos = []
        if attachments:
            msg_att_dir = os.path.join(self.attachments_dir, msg_id)
            os.makedirs(msg_att_dir, exist_ok=True)
            for idx, (orig_name, data) in enumerate(attachments):
                safe_name = f"{idx}_{orig_name}"
                filepath = os.path.join(msg_att_dir, safe_name)
                with open(filepath, "wb") as f:
                    f.write(data)
                attachment_infos.append({
                    "name": orig_name,
                    "size": len(data),
                    "stored": safe_name,
                    "mime": self._guess_mime(orig_name)
                })

        msg = Message(
            filename=msg_id,
            sender=sender,
            recipient=recipient,
            subject=subject,
            body_raw=final_body,
            date=timestamp,
            is_encrypted=(encryption_mode is not None),
            encryption_type=encryption_mode,
            stego_key_hex=None,
            attachments=attachment_infos
        )
        self._save_message_file(msg)

        # ========== ОСНОВНОЕ ИСПРАВЛЕНИЕ: ДЛЯ ПИСЕМ СЕБЕ – ТОЛЬКО ОДНА ЗАПИСЬ ==========
        if sender == recipient:
            # Письмо самому себе – добавляем только одну запись (например, в папку "inbox")
            idx = self._load_user_index(sender)
            idx["messages"].append({
                "id": msg_id,
                "folder": "inbox",          # можно заменить на "sent", если нужно видеть в исходящих
                "is_read": False,
                "is_deleted": False,
                "timestamp": timestamp
            })
            self._save_user_index(sender, idx)
        else:
            # Обычная логика для разных отправителя и получателя
            sender_index = self._load_user_index(sender)
            sender_index["messages"].append({
                "id": msg_id,
                "folder": "sent",
                "is_read": True,
                "is_deleted": False,
                "timestamp": timestamp
            })
            self._save_user_index(sender, sender_index)

            recipient_index = self._load_user_index(recipient)
            recipient_index["messages"].append({
                "id": msg_id,
                "folder": "inbox",
                "is_read": False,
                "is_deleted": False,
                "timestamp": timestamp
            })
            self._save_user_index(recipient, recipient_index)

        return True, "Письмо отправлено"

    def _guess_mime(self, filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        mime_map = {
            '.txt': 'text/plain',
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.zip': 'application/zip',
        }
        return mime_map.get(ext, 'application/octet-stream')

    def get_messages_list(self, login: str) -> List[Message]:
        index = self._load_user_index(login)
        messages = []
        for entry in index["messages"]:
            if entry.get("is_deleted", False):
                continue
            msg = self._load_message_file(entry["id"])
            if msg is None:
                continue
            msg.folder = entry.get("folder", "inbox")
            msg.is_read = entry.get("is_read", False)
            messages.append(msg)

        # Разделяем на имеющие дату и не имеющие
        with_date = [m for m in messages if m.date is not None]
        without_date = [m for m in messages if m.date is None]
        with_date.sort(key=lambda m: m.date, reverse=True)
        return with_date + without_date

    def get_message_body(self, msg_id: str) -> Optional[str]:
        msg = self._load_message_file(msg_id)
        return msg.body_raw if msg else None

    def mark_as_read(self, login: str, msg_id: str) -> bool:
        index = self._load_user_index(login)
        for entry in index["messages"]:
            if entry["id"] == msg_id:
                if not entry.get("is_read", False):
                    entry["is_read"] = True
                    self._save_user_index(login, index)
                return True
        return False

    def delete_message(self, login: str, msg_id: str) -> bool:
        index = self._load_user_index(login)
        for entry in index["messages"]:
            if entry["id"] == msg_id:
                entry["is_deleted"] = True
                self._save_user_index(login, index)
                self._cleanup_orphaned_attachments(msg_id)
                return True
        return False

    def delete_all_messages(self, login: str) -> int:
        index = self._load_user_index(login)
        count = 0
        for entry in index["messages"]:
            if not entry.get("is_deleted", False):
                entry["is_deleted"] = True
                count += 1
        if count:
            self._save_user_index(login, index)
        return count

    def _cleanup_orphaned_attachments(self, msg_id: str):
        msg = self._load_message_file(msg_id)
        if not msg:
            return
        sender_idx = self._load_user_index(msg.sender)
        recipient_idx = self._load_user_index(msg.recipient)
        sender_deleted = any(e["id"] == msg_id and e.get("is_deleted") for e in sender_idx["messages"])
        recipient_deleted = any(e["id"] == msg_id and e.get("is_deleted") for e in recipient_idx["messages"])
        if sender_deleted and recipient_deleted:
            att_path = os.path.join(self.attachments_dir, msg_id)
            if os.path.exists(att_path):
                shutil.rmtree(att_path)
            os.remove(os.path.join(self.messages_dir, f"{msg_id}.json"))

    def save_attachment(self, msg_id: str, attachment_name: str, target_path: str) -> bool:
        msg = self._load_message_file(msg_id)
        if not msg:
            return False
        for att in msg.attachments:
            if att["name"] == attachment_name:
                src = os.path.join(self.attachments_dir, msg_id, att["stored"])
                if os.path.exists(src):
                    shutil.copy2(src, target_path)
                    return True
        return False

    def decrypt_message_body(self, message: Message, **kwargs) -> str:
        """Расшифрование тела сообщения"""
        if not message.encryption_type:
            return message.body_raw

        if message.encryption_type == "aes":
            aes_key = kwargs.get('aes_key')
            if not aes_key:
                raise ValueError("Нужен ключ AES")
            from encryption.aes_cipher import AESCipher
            return AESCipher.decrypt(aes_key, message.body_raw)

        if message.encryption_type == "time":
            time_salt = kwargs.get('time_salt')
            time_bucket = kwargs.get('time_bucket')
            if not time_salt or not time_bucket:
                raise ValueError("Нужны соль и временной интервал")
            from encryption.time_cipher import TimeCipher
            return TimeCipher.decrypt(message.body_raw, time_salt, time_bucket)

        return message.body_raw