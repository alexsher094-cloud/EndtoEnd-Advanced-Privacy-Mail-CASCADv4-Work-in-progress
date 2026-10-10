import sqlite3
import queue
import hashlib
import os
import uuid
from typing import Optional, List, Dict, Any, Tuple
from config import ServerConfig


class SQLitePool:
    """Пул соединений SQLite с оптимизированными прагмами"""

    def __init__(self, db_path: str, max_connections: int = 10):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool = queue.Queue(max_connections)
        self._init_pool()

    def _init_pool(self):
        for _ in range(self.max_connections):
            conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-20000")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA busy_timeout=5000")
            self._pool.put(conn)

    def get_connection(self) -> sqlite3.Connection:
        return self._pool.get()

    def return_connection(self, conn: sqlite3.Connection):
        self._pool.put(conn)

    def execute(self, query: str, params=()) -> sqlite3.Cursor:
        conn = self.get_connection()
        try:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor
        finally:
            self.return_connection(conn)

    def executemany(self, query: str, seq_of_params) -> sqlite3.Cursor:
        conn = self.get_connection()
        try:
            cursor = conn.executemany(query, seq_of_params)
            conn.commit()
            return cursor
        finally:
            self.return_connection(conn)

    def close_all(self):
        while not self._pool.empty():
            conn = self._pool.get()
            conn.close()


class Database:
    def __init__(self, db_path: str = ServerConfig.DB_PATH):
        self.db_path = db_path
        self.pool = SQLitePool(db_path, max_connections=ServerConfig.DB_POOL_SIZE)
        self._init_tables()

    def _init_tables(self):
        conn = self.pool.get_connection()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    login TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid TEXT UNIQUE NOT NULL,
                    sender TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    subject TEXT,
                    body TEXT,
                    encryption_type TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    data BLOB NOT NULL,
                    mime_type TEXT,
                    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
                );
                
                CREATE TABLE IF NOT EXISTS user_messages (
                    user_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    folder TEXT NOT NULL CHECK (folder IN ('inbox', 'sent')),
                    is_read BOOLEAN DEFAULT 0,
                    is_deleted BOOLEAN DEFAULT 0,
                    PRIMARY KEY (user_id, message_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
                );
                
                CREATE INDEX IF NOT EXISTS idx_user_messages_user ON user_messages(user_id);
                CREATE INDEX IF NOT EXISTS idx_user_messages_message ON user_messages(message_id);
                CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender);
                CREATE INDEX IF NOT EXISTS idx_messages_recipient ON messages(recipient);
            """)
            conn.commit()
        finally:
            self.pool.return_connection(conn)

    def _hash_password(self, password: str) -> str:
        salt = os.urandom(32)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        return salt.hex() + ':' + pwd_hash.hex()

    def _verify_password(self, stored: str, provided: str) -> bool:
        try:
            salt_hex, hash_hex = stored.split(':')
            salt = bytes.fromhex(salt_hex)
            pwd_hash = hashlib.pbkdf2_hmac('sha256', provided.encode(), salt, 100000)
            return pwd_hash.hex() == hash_hex
        except Exception:
            return False

    def _get_user_id(self, login: str) -> Optional[int]:
        row = self.pool.execute("SELECT id FROM users WHERE login = ?", (login,)).fetchone()
        return row['id'] if row else None

    def register_user(self, login: str, password: str) -> Tuple[bool, str]:
        try:
            self.pool.execute(
                "INSERT INTO users (login, password_hash) VALUES (?, ?)",
                (login, self._hash_password(password))
            )
            return True, "OK"
        except sqlite3.IntegrityError:
            return False, "Пользователь уже существует"

    def authenticate(self, login: str, password: str) -> bool:
        row = self.pool.execute(
            "SELECT password_hash FROM users WHERE login = ?", (login,)
        ).fetchone()
        if not row:
            return False
        return self._verify_password(row['password_hash'], password)

    def user_exists(self, login: str) -> bool:
        row = self.pool.execute("SELECT 1 FROM users WHERE login = ?", (login,)).fetchone()
        return row is not None

    # ---------- ИСПРАВЛЕННЫЙ МЕТОД ОТПРАВКИ ----------
    def send_message(self, sender: str, recipient: str, subject: str, body: str,
                     encryption_type: Optional[str] = None,
                     attachments: Optional[List[Tuple[str, bytes, str]]] = None) -> Tuple[bool, str, Optional[int]]:
        if not self.user_exists(recipient):
            return False, f"Получатель '{recipient}' не существует", None

        msg_uuid = str(uuid.uuid4())
        try:
            cursor = self.pool.execute(
                """INSERT INTO messages (uuid, sender, recipient, subject, body, encryption_type)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (msg_uuid, sender, recipient, subject, body, encryption_type)
            )
            message_id = cursor.lastrowid
        except Exception as e:
            return False, f"Ошибка БД: {e}", None

        if attachments:
            self.pool.executemany(
                "INSERT INTO attachments (message_id, filename, data, mime_type) VALUES (?, ?, ?, ?)",
                [(message_id, name, data, mime) for name, data, mime in attachments]
            )

        sender_id = self._get_user_id(sender)
        recipient_id = self._get_user_id(recipient)

        # Корректная логика для писем самому себе
        if sender_id == recipient_id:
            self.pool.execute(
                "INSERT INTO user_messages (user_id, message_id, folder, is_read) VALUES (?, ?, 'inbox', 0)",
                (sender_id, message_id)
            )
        else:
            if sender_id:
                self.pool.execute(
                    "INSERT INTO user_messages (user_id, message_id, folder, is_read) VALUES (?, ?, 'sent', 1)",
                    (sender_id, message_id)
                )
            if recipient_id:
                self.pool.execute(
                    "INSERT INTO user_messages (user_id, message_id, folder, is_read) VALUES (?, ?, 'inbox', 0)",
                    (recipient_id, message_id)
                )

        return True, "Письмо отправлено", message_id
    # ----------------------------------------------

    def get_messages_list(self, login: str, folder: Optional[str] = None) -> List[Dict]:
        user_id = self._get_user_id(login)
        if not user_id:
            return []

        query = """
            SELECT m.id, m.uuid, m.sender, m.recipient, m.subject, m.body, 
                   m.encryption_type, m.timestamp, 
                   um.folder, um.is_read, um.is_deleted,
                   (SELECT COUNT(*) FROM attachments WHERE message_id = m.id) as has_attachments
            FROM messages m
            JOIN user_messages um ON m.id = um.message_id
            WHERE um.user_id = ? AND um.is_deleted = 0
        """
        params = [user_id]
        if folder:
            query += " AND um.folder = ?"
            params.append(folder)
        query += " ORDER BY m.timestamp DESC"

        rows = self.pool.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_message_by_id(self, message_id: int, login: str) -> Optional[Dict]:
        user_id = self._get_user_id(login)
        if not user_id:
            return None

        row = self.pool.execute("""
            SELECT m.*, um.folder, um.is_read
            FROM messages m
            JOIN user_messages um ON m.id = um.message_id
            WHERE m.id = ? AND um.user_id = ? AND um.is_deleted = 0
        """, (message_id, user_id)).fetchone()
        if not row:
            return None

        msg = dict(row)
        attachments = self.pool.execute(
            "SELECT id, filename, mime_type, LENGTH(data) as size FROM attachments WHERE message_id = ?",
            (message_id,)
        ).fetchall()
        msg['attachments'] = [dict(a) for a in attachments]
        return msg

    def get_attachment_data(self, attachment_id: int, login: str) -> Optional[bytes]:
        row = self.pool.execute("""
            SELECT a.data FROM attachments a
            JOIN messages m ON a.message_id = m.id
            JOIN user_messages um ON m.id = um.message_id
            JOIN users u ON um.user_id = u.id
            WHERE a.id = ? AND u.login = ? AND um.is_deleted = 0
        """, (attachment_id, login)).fetchone()
        return row['data'] if row else None

    def mark_as_read(self, login: str, message_id: int) -> bool:
        user_id = self._get_user_id(login)
        if not user_id:
            return False
        self.pool.execute(
            "UPDATE user_messages SET is_read = 1 WHERE user_id = ? AND message_id = ?",
            (user_id, message_id)
        )
        return True

    def delete_message(self, login: str, message_id: int) -> bool:
        user_id = self._get_user_id(login)
        if not user_id:
            return False
        self.pool.execute(
            "UPDATE user_messages SET is_deleted = 1 WHERE user_id = ? AND message_id = ?",
            (user_id, message_id)
        )
        return True

    def delete_all_messages(self, login: str) -> int:
        user_id = self._get_user_id(login)
        if not user_id:
            return 0
        cursor = self.pool.execute(
            "UPDATE user_messages SET is_deleted = 1 WHERE user_id = ? AND is_deleted = 0",
            (user_id,)
        )
        return cursor.rowcount

    def delete_user(self, login: str) -> bool:
        user_id = self._get_user_id(login)
        if not user_id:
            return False
        self.pool.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return True

    def get_online_users(self, active_logins: set) -> List[str]:
        if not active_logins:
            return []
        placeholders = ','.join('?' for _ in active_logins)
        rows = self.pool.execute(
            f"SELECT login FROM users WHERE login IN ({placeholders})",
            list(active_logins)
        ).fetchall()
        return [row['login'] for row in rows]