# models/message.py
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime
import re

@dataclass
class Message:
    filename: str               # UUID
    sender: str
    recipient: str
    subject: str
    body_raw: str               # может быть зашифрован
    date: Optional[str] = None
    preview: str = ""
    is_encrypted: bool = False
    folder: str = "inbox"       # "inbox" или "sent"
    is_read: bool = False
    encryption_type: Optional[str] = None   # 'aes', 'time', None
    stego_key_hex: Optional[str] = None
    attachments: List[Dict] = field(default_factory=list)  # см. структуру ниже
    server_id: Optional[int] = None          # числовой ID на сервере
    has_attachments_flag: bool = False       # признак наличия вложений

    def __post_init__(self):
        if not self.date:
            self.date = datetime.now().isoformat()
        if not self.preview:
            if self.is_encrypted:
                self.preview = "[ЗАШИФРОВАНО]"
            else:
                self.preview = self.body_raw.replace('\n', ' ')[:50]
                if len(self.body_raw) > 50:
                    self.preview += "..."

    @property
    def display_subject(self) -> str:
        prefix = "● " if (self.folder == "inbox" and not self.is_read) else ""
        if self.is_encrypted:
            return f"{prefix}[Зашифровано] {self.subject}"
        return f"{prefix}{self.subject}"

    # Стеганография (оставляем как было)
    STEGO_PATTERN = re.compile(r'\n?\[STEGO_KEY\](.*?)\[/STEGO_KEY\]', re.DOTALL)

    @property
    def has_stego(self) -> bool:
        return bool(self.STEGO_PATTERN.search(self.body_raw))

    def get_stego_key_hex(self) -> Optional[str]:
        m = self.STEGO_PATTERN.search(self.body_raw)
        return m.group(1).strip() if m else None

    @property
    def clean_body(self) -> str:
        return self.STEGO_PATTERN.sub('', self.body_raw).strip()

    def has_attachments(self) -> bool:
        return len(self.attachments) > 0
    
    @property
    def display_date(self) -> str:
        return "дата скрыта" if self.is_encrypted else (self.date or "неизвестно")