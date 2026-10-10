# storage/network_repo.py
import socket
import ssl
import json
import os
import threading
import time
import base64
import logging
from typing import List, Tuple, Optional
from models.message import Message
from encryption.aes_cipher import AESCipher
from encryption.time_cipher import TimeCipher

logger = logging.getLogger(__name__)


class NetworkRepository:
    def __init__(self, server: str, port: int, use_tls: bool = True):
        self.server = server
        self.port = port
        self.use_tls = use_tls
        self.sock = None
        self.login = None
        self._cached_password = None

        # RLock — реентерабельный, можно захватывать многократно из одного потока
        self.lock = threading.RLock()

        # Таймауты
        self.connect_timeout = 10
        self.recv_timeout = 20

        self._connect()

    # ============================================================
    # ПОДКЛЮЧЕНИЕ
    # ============================================================
    def _connect(self):
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw.settimeout(self.connect_timeout)
        raw.connect((self.server, self.port))

        if self.use_tls:
            ctx = ssl._create_unverified_context()
            self.sock = ctx.wrap_socket(raw, server_hostname=self.server)
        else:
            self.sock = raw

        self.sock.settimeout(self.recv_timeout)

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _reconnect(self):
        """Переподключение без рекурсии в _send_request."""
        # Закрываем старый сокет
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

        # Открываем заново
        self._connect()

        # Если были залогинены — повторяем логин напрямую (не через _send_request)
        if self.login and self._cached_password:
            try:
                self.sock.sendall((json.dumps({
                    "action": "login",
                    "login": self.login,
                    "password": self._cached_password,
                }) + '\n').encode())

                data = self.sock.recv(65536).decode()
                for line in data.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    msg = json.loads(line)
                    if msg.get("status") == "ok":
                        logger.info(f"Re-login OK: {self.login}")
                        return
                raise Exception("Re-login failed")
            except Exception as e:
                self.login = None
                raise ConnectionError(f"Re-login failed: {e}")

    # ============================================================
    # ОТПРАВКА ЗАПРОСА
    # ============================================================
    def _send_request(self, req: dict) -> dict:
        with self.lock:
            for attempt in range(2):
                try:
                    if not self.sock:
                        self._connect()

                    # Отправляем
                    self.sock.sendall((json.dumps(req) + '\n').encode())

                    # Читаем ответ (пропуская уведомления)
                    start = time.time()
                    while time.time() - start < self.recv_timeout:
                        try:
                            data = self.sock.recv(65536).decode()
                        except socket.timeout:
                            raise TimeoutError(f"Сервер не ответил за {self.recv_timeout} сек")

                        if not data:
                            raise ConnectionError("Пустой ответ от сервера")

                        for line in data.split('\n'):
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                msg = json.loads(line)
                            except json.JSONDecodeError:
                                continue

                            # Уведомление — пропускаем
                            if "event" in msg and "status" not in msg:
                                logger.debug(f"Пропущено уведомление: {msg.get('event')}")
                                continue

                            # Настоящий ответ
                            return msg

                    raise TimeoutError("Общий таймаут ожидания ответа")

                except (socket.error, ssl.SSLError, TimeoutError, ConnectionError) as e:
                    logger.warning(f"Ошибка соединения (попытка {attempt + 1}): {e}")
                    if attempt == 0:
                        try:
                            self._reconnect()
                        except Exception as re:
                            raise ConnectionError(f"Не удалось переподключиться: {re}")
                        continue
                    raise ConnectionError(f"Server error: {e}")

        return {"status": "error", "error": "Unknown error"}

    # ============================================================
    # ПУБЛИЧНЫЕ МЕТОДЫ
    # ============================================================
    def ping(self) -> bool:
        try:
            resp = self._send_request({"action": "ping"})
            return resp.get("status") == "pong"
        except Exception as e:
            logger.debug(f"Ping failed: {e}")
            return False

    def authenticate(self, login: str, password: str) -> Tuple[bool, str]:
        try:
            resp = self._send_request({
                "action": "login",
                "login": login,
                "password": password,
            })
            if resp.get("status") == "ok":
                self.login = login
                self._cached_password = password
                return True, "OK"
            return False, resp.get("error", "Unknown error")
        except Exception as e:
            return False, str(e)

    def register_user(self, login: str, password: str) -> Tuple[bool, str]:
        try:
            resp = self._send_request({
                "action": "register",
                "login": login,
                "password": password,
            })
            if resp.get("status") == "ok":
                return True, "Registered"
            return False, resp.get("error", "Unknown error")
        except Exception as e:
            return False, str(e)

    def send_message(self, sender: str, recipient: str, subject: str, body: str,
                     encryption_mode: Optional[str] = None,
                     aes_key: Optional[bytes] = None,
                     time_salt: Optional[str] = None,
                     time_bucket: Optional[str] = None,
                     attachments: Optional[List[Tuple[str, bytes]]] = None) -> Tuple[bool, str]:
        final_body = body
        if encryption_mode == "aes" and aes_key:
            final_body = AESCipher.encrypt(aes_key, body)
        elif encryption_mode == "time" and time_salt and time_bucket:
            final_body = TimeCipher.encrypt(body, time_salt, time_bucket)

        att_list = []
        if attachments:
            for name, data in attachments:
                att_list.append({
                    "name": name,
                    "data": base64.b64encode(data).decode(),
                    "mime_type": self._guess_mime(name),
                })

        req = {
            "action": "send",
            "login": sender,
            "sender": sender,
            "recipient": recipient,
            "subject": subject,
            "body": final_body,
            "attachments": att_list,
        }
        if encryption_mode:
            req["encryption_type"] = encryption_mode

        try:
            resp = self._send_request(req)
            if resp.get("status") == "ok":
                return True, "Sent"
            return False, resp.get("error", "Unknown error")
        except Exception as e:
            return False, str(e)

    def get_messages_list(self, login: str) -> List[Message]:
        try:
            resp = self._send_request({
                "action": "list_messages",
                "login": login,
            })
            if resp.get("status") != "ok":
                logger.error(f"list_messages error: {resp.get('error')}")
                return []

            messages = []
            for item in resp.get("result", []):
                msg = Message(
                    filename=item.get("uuid"),
                    sender=item["sender"],
                    recipient=item["recipient"],
                    subject=item["subject"],
                    body_raw="",
                    date=item.get("timestamp"),
                    is_encrypted=bool(item.get("encryption_type")),
                    encryption_type=item.get("encryption_type"),
                    folder="inbox" if item["recipient"] == login else "sent",
                    is_read=False,
                    attachments=[],
                )
                msg.server_id = item["id"]
                msg.has_attachments_flag = item.get("has_attachments", 0) > 0
                messages.append(msg)
            return messages
        except Exception as e:
            logger.error(f"list_messages error: {e}")
            return []

    def get_full_message(self, msg: Message) -> Optional[Message]:
        try:
            resp = self._send_request({
                "action": "get_message",
                "login": self.login,
                "message_id": msg.server_id,
            })
            if resp.get("status") != "ok":
                return None

            data = resp["result"]
            msg.body_raw = data["body"]
            atts = []
            for att in data.get("attachments", []):
                atts.append({
                    "id": att["id"],
                    "name": att["filename"],
                    "size": att.get("size", 0),
                    "mime_type": att.get("mime_type", ""),
                })
            msg.attachments = atts
            msg.is_read = data.get("is_read", False)
            return msg
        except Exception as e:
            logger.error(f"get_message error: {e}")
            return None

    def mark_message_as_read(self, message: Message) -> bool:
        try:
            resp = self._send_request({
                "action": "mark_read",
                "login": self.login,
                "message_id": message.server_id,
            })
            return resp.get("status") == "ok"
        except Exception:
            return False

    def delete_message_by_server_id(self, server_id: int) -> bool:
        try:
            resp = self._send_request({
                "action": "delete_message",
                "login": self.login,
                "message_id": server_id,
            })
            return resp.get("status") == "ok"
        except Exception:
            return False

    def delete_all_messages(self, login: str) -> int:
        try:
            resp = self._send_request({
                "action": "delete_all_messages",
                "login": login,
            })
            if resp.get("status") == "ok":
                return resp.get("result", {}).get("deleted_count", 0)
            return 0
        except Exception:
            return 0

    def delete_user(self, login: str) -> bool:
        return False

    def download_attachment(self, attachment_id: int, target_path: str) -> bool:
        try:
            resp = self._send_request({
                "action": "get_attachment",
                "login": self.login,
                "attachment_id": attachment_id,
            })
            if resp.get("status") != "ok":
                logger.error(f"get_attachment error: {resp.get('error')}")
                return False

            data_b64 = resp["result"]["data"]
            file_data = base64.b64decode(data_b64)
            with open(target_path, "wb") as f:
                f.write(file_data)
            return True
        except Exception as e:
            logger.error(f"download_attachment error: {e}")
            return False

    def decrypt_message_body(self, message: Message, **kwargs) -> str:
        if not message.encryption_type:
            return message.body_raw
        if message.encryption_type == "aes":
            aes_key = kwargs.get("aes_key")
            if not aes_key:
                raise ValueError("AES key required")
            return AESCipher.decrypt(aes_key, message.body_raw)
        if message.encryption_type == "time":
            time_salt = kwargs.get("time_salt")
            time_bucket = kwargs.get("time_bucket")
            if not time_salt or not time_bucket:
                raise ValueError("Salt and time bucket required")
            return TimeCipher.decrypt(message.body_raw, time_salt, time_bucket)
        return message.body_raw

    @staticmethod
    def _guess_mime(filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        mime_map = {
            ".txt": "text/plain",
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".zip": "application/zip",
        }
        return mime_map.get(ext, "application/octet-stream")