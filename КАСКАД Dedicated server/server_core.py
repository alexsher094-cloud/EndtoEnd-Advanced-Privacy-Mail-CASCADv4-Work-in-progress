# server_core.py
import socket
import ssl
import threading
import json
import logging
import base64
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Tuple
from config import ServerConfig
from database import Database

logger = logging.getLogger(__name__)

MAX_REQUEST_SIZE = 10 * 1024 * 1024
MAX_MESSAGE_BODY = 10 * 1024 * 1024
MAX_ATTACHMENTS_TOTAL = 50 * 1024 * 1024
MAX_ATTACHMENTS_COUNT = 20
MAX_FAILED_ATTEMPTS = 5
BLOCK_TIME_SECONDS = 60


class MailServer:
    def __init__(self, host: str = ServerConfig.DEFAULT_HOST, port: int = ServerConfig.DEFAULT_PORT,
                 max_workers: int = ServerConfig.MAX_WORKERS,
                 use_tls: bool = False, certfile: Optional[str] = None, keyfile: Optional[str] = None):
        self.host = host
        self.port = port
        self.max_workers = max_workers
        self.use_tls = use_tls
        self.certfile = certfile
        self.keyfile = keyfile
        self.socket = None
        self.running = False
        self.executor = None
        self.db = Database()
        self.active_sessions: Dict[str, Tuple[socket.socket, Tuple]] = {}
        self.lock = threading.Lock()
        self.failed_attempts: Dict[str, Tuple[int, float]] = {}
        self.failed_lock = threading.Lock()
        self.ip_connections: Dict[str, int] = {}
        self.ip_lock = threading.Lock()
        self.max_connections_per_ip = 10

    def start(self):
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        try:
            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            raw_sock.bind((self.host, self.port))
            raw_sock.settimeout(1.0)
            raw_sock.listen(ServerConfig.SOCKET_BACKLOG)

            if self.use_tls:
                if not self.certfile or not self.keyfile:
                    raise ValueError("Для TLS необходимо указать certfile и keyfile")
                context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                context.load_cert_chain(certfile=self.certfile, keyfile=self.keyfile)
                self.socket = context.wrap_socket(raw_sock, server_side=True)
                logger.info(f"🔒 TLS включён, сертификат: {self.certfile}")
            else:
                self.socket = raw_sock
                logger.warning("🔓 TLS отключён! Пароли и данные передаются в открытом виде.")

            self.running = True
            logger.info(f"✅ Сервер запущен на {self.host}:{self.port}")

            while self.running:
                try:
                    conn, addr = self.socket.accept()
                    ip = addr[0]
                    with self.ip_lock:
                        current = self.ip_connections.get(ip, 0)
                        if current >= self.max_connections_per_ip:
                            logger.warning(f"Слишком много соединений с {ip}, отклонено")
                            conn.close()
                            continue
                        self.ip_connections[ip] = current + 1
                    logger.info(f"🔌 Новое соединение из {addr}")
                    self.executor.submit(self._handle_client, conn, addr)
                except socket.timeout:
                    continue
                except OSError as e:
                    if self.running:
                        logger.error(f"Ошибка accept: {e}")
                    break
                except Exception as e:
                    logger.error(f"Неожиданная ошибка: {e}")
        except OSError as e:
            logger.error(f"❌ Не удалось запустить сервер: {e}")
            self.running = False
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            self.running = False

    def stop(self):
        logger.info("Остановка сервера...")
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        with self.lock:
            for conn, _ in self.active_sessions.items():
                try:
                    conn.close()
                except:
                    pass
            self.active_sessions.clear()
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)
        logger.info("⏹ Сервер остановлен")

    def _handle_client(self, conn: socket.socket, addr):
        conn.settimeout(5.0)
        login = None
        buffer = ""
        total_buffer = 0
        try:
            while self.running:
                try:
                    data = conn.recv(4096).decode('utf-8')
                    if not data:
                        break
                except socket.timeout:
                    continue
                except (ConnectionResetError, BrokenPipeError, OSError):
                    break

                buffer += data
                total_buffer += len(data)

                if total_buffer > MAX_REQUEST_SIZE:
                    logger.warning(f"Превышен размер запроса от {addr}, соединение закрыто")
                    try:
                        conn.sendall(json.dumps({"status": "error", "error": "Request too large"}).encode('utf-8') + b'\n')
                    except:
                        pass
                    break

                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    total_buffer -= len(line) + 1
                    if line.strip():
                        try:
                            request = json.loads(line)
                            response = self._process_request(request, conn, addr)
                            if response:
                                conn.sendall((json.dumps(response) + '\n').encode('utf-8'))
                        except json.JSONDecodeError as e:
                            logger.error(f"Неверный JSON от {addr}: {e}")
                            try:
                                conn.sendall(json.dumps({"status": "error", "error": "Invalid JSON"}).encode('utf-8') + b'\n')
                            except:
                                pass
        except (socket.timeout, ConnectionResetError, BrokenPipeError, OSError) as e:
            logger.info(f"Потеря связи с {addr}: {e}")
        except Exception as e:
            logger.error(f"Ошибка в обработчике {addr}: {e}")
        finally:
            ip = addr[0]
            with self.ip_lock:
                cnt = self.ip_connections.get(ip, 0)
                if cnt > 0:
                    self.ip_connections[ip] = cnt - 1
            with self.lock:
                if login and login in self.active_sessions:
                    if self.active_sessions[login][0] is conn:
                        del self.active_sessions[login]
            try:
                conn.close()
            except:
                pass
            logger.info(f"Клиент отключён: {addr}")

    def _check_auth(self, login: str, conn: socket.socket) -> bool:
        with self.lock:
            stored_conn, _ = self.active_sessions.get(login, (None, None))
            return stored_conn is not None and stored_conn is conn

    def _is_ip_blocked(self, ip: str) -> bool:
        with self.failed_lock:
            fails, last_time = self.failed_attempts.get(ip, (0, 0))
            return fails >= MAX_FAILED_ATTEMPTS and (time.time() - last_time) < BLOCK_TIME_SECONDS

    def _register_failed_attempt(self, ip: str):
        with self.failed_lock:
            fails, _ = self.failed_attempts.get(ip, (0, 0))
            self.failed_attempts[ip] = (fails + 1, time.time())

    def _reset_failed_attempts(self, ip: str):
        with self.failed_lock:
            self.failed_attempts.pop(ip, None)

    # ============================================================
    # ОСНОВНОЙ ОБРАБОТЧИК ЗАПРОСОВ
    # ============================================================
    def _process_request(self, req: dict, conn: socket.socket, addr) -> dict:
        action = req.get('action')
        logger.debug(f"Запрос от {addr}: {action}")

        # Проверка авторизации для всех действий, кроме регистрации/логина/ping
        if action not in ("register", "login", "ping"):
            login = req.get('login')
            if not login or not self._check_auth(login, conn):
                return {"status": "error", "error": "Not authenticated"}

        # ---------- REGISTER ----------
        if action == "register":
            login = req.get('login', '').strip()
            password = req.get('password', '')
            if not login or not password:
                return {"status": "error", "error": "Логин и пароль обязательны"}
            if self._is_ip_blocked(addr[0]):
                return {"status": "error", "error": "Too many attempts. Try later."}
            success, msg = self.db.register_user(login, password)
            if not success:
                self._register_failed_attempt(addr[0])
            else:
                self._reset_failed_attempts(addr[0])
            return {"status": "ok" if success else "error", "error": msg if not success else None}

        # ---------- LOGIN ----------
        elif action == "login":
            login = req.get('login', '').strip()
            password = req.get('password', '')
            ip = addr[0]
            if not login or not password:
                return {"status": "error", "error": "Логин и пароль обязательны"}
            if self._is_ip_blocked(ip):
                return {"status": "error", "error": "Too many failed attempts. Try later."}
            if self.db.authenticate(login, password):
                with self.lock:
                    if login in self.active_sessions:
                        old_conn, old_addr = self.active_sessions[login]
                        try:
                            old_conn.close()
                        except:
                            pass
                    self.active_sessions[login] = (conn, addr)
                self._reset_failed_attempts(ip)
                logger.info(f"Пользователь {login} вошёл с {addr}")
                return {"status": "ok", "result": {"login": login}}
            else:
                self._register_failed_attempt(ip)
                logger.warning(f"Неудачная попытка входа {login} с {addr}")
                return {"status": "error", "error": "Неверный логин или пароль"}

        # ---------- PING ----------
        elif action == "ping":
            return {"status": "pong"}

        # ---------- SEND ----------
        elif action == "send":
            sender = req.get('sender')
            recipient = req.get('recipient')
            subject = req.get('subject', '')
            body = req.get('body', '')
            encryption_type = req.get('encryption_type')
            attachments_raw = req.get('attachments', [])

            if len(body) > MAX_MESSAGE_BODY:
                return {"status": "error", "error": f"Body exceeds {MAX_MESSAGE_BODY//1024//1024} MB"}

            if len(attachments_raw) > MAX_ATTACHMENTS_COUNT:
                return {"status": "error", "error": f"Too many attachments (max {MAX_ATTACHMENTS_COUNT})"}

            attachments = []
            total_size = 0
            for att in attachments_raw:
                name = att.get('name', 'file')
                data_b64 = att.get('data', '')
                mime = att.get('mime_type', 'application/octet-stream')
                try:
                    data = base64.b64decode(data_b64)
                    total_size += len(data)
                    if total_size > MAX_ATTACHMENTS_TOTAL:
                        return {"status": "error", "error": "Total attachments size too large"}
                    attachments.append((name, data, mime))
                except Exception as e:
                    return {"status": "error", "error": f"Ошибка вложения {name}: {e}"}

            # Отправляем письмо в БД
            success, msg, msg_id = self.db.send_message(
                sender, recipient, subject, body, encryption_type, attachments
            )

            # Уведомляем получателя (если онлайн)
            if success and msg_id and sender != recipient:
                with self.lock:
                    recipient_info = self.active_sessions.get(recipient)

                if recipient_info:
                    recipient_conn, _ = recipient_info
                    try:
                        notification = {
                            "event": "new_message",
                            "data": {
                                "message_id": msg_id,
                                "from": sender,
                                "subject": subject
                            }
                        }
                        recipient_conn.sendall((json.dumps(notification) + '\n').encode())
                        logger.info(f"📨 Уведомление отправлено {recipient}")
                    except Exception as e:
                        # Мёртвый сокет — удаляем сессию получателя
                        logger.warning(f"Мёртвый сокет у {recipient}: {e}. Удаляю сессию.")
                        with self.lock:
                            if recipient in self.active_sessions and self.active_sessions[recipient][0] is recipient_conn:
                                self.active_sessions.pop(recipient, None)

            return {"status": "ok" if success else "error", "error": msg if not success else None}

        # ---------- LIST_MESSAGES ----------
        elif action == "list_messages":
            login = req.get('login')
            folder = req.get('folder')
            messages = self.db.get_messages_list(login, folder)
            # Убираем тело из списка (оно тяжелое, грузится отдельно)
            for m in messages:
                m.pop('body', None)
            return {"status": "ok", "result": messages}

        # ---------- GET_MESSAGE ----------
        elif action == "get_message":
            login = req.get('login')
            message_id = req.get('message_id')
            msg = self.db.get_message_by_id(message_id, login)
            if not msg:
                return {"status": "error", "error": "Сообщение не найдено"}
            for att in msg['attachments']:
                att.pop('data', None)
            return {"status": "ok", "result": msg}

        # ---------- GET_ATTACHMENT ----------
        elif action == "get_attachment":
            login = req.get('login')
            attachment_id = req.get('attachment_id')
            data = self.db.get_attachment_data(attachment_id, login)
            if data is None:
                return {"status": "error", "error": "Вложение не найдено или доступ запрещён"}
            return {"status": "ok", "result": {"data": base64.b64encode(data).decode()}}

        # ---------- MARK_READ ----------
        elif action == "mark_read":
            login = req.get('login')
            message_id = req.get('message_id')
            self.db.mark_as_read(login, message_id)
            return {"status": "ok"}

        # ---------- DELETE_MESSAGE ----------
        elif action == "delete_message":
            login = req.get('login')
            message_id = req.get('message_id')
            success = self.db.delete_message(login, message_id)
            return {"status": "ok" if success else "error",
                    "error": "Не удалось удалить" if not success else None}

        # ---------- DELETE_ALL_MESSAGES ----------
        elif action == "delete_all_messages":
            login = req.get('login')
            count = self.db.delete_all_messages(login)
            return {"status": "ok", "result": {"deleted_count": count}}

        # ---------- LOGOUT ----------
        elif action == "logout":
            login = req.get('login')
            with self.lock:
                if login in self.active_sessions:
                    del self.active_sessions[login]
            return {"status": "ok"}

        # ---------- UNKNOWN ----------
        else:
            return {"status": "error", "error": f"Неизвестное действие: {action}"}

    def get_stats(self) -> dict:
        with self.lock:
            active_logins = list(self.active_sessions.keys())
        online_users = self.db.get_online_users(set(active_logins))
        return {
            "running": self.running,
            "active_connections": len(self.active_sessions),
            "online_users": online_users,
            "max_workers": self.max_workers
        }