# gui/compose_view.py
import customtkinter as ctk
import secrets
import base64
import datetime
import os
from typing import Optional, Callable, List, Tuple
from .styles import Styles
from utils.clipboard import ClipboardManager
from utils.validators import Validators

class ComposeView(ctk.CTkToplevel):
    """Окно создания нового письма"""
    
    def __init__(self, parent, sender: str, on_send: Callable):
        super().__init__(parent)
        self.parent = parent
        self.sender = sender
        self.on_send = on_send
        
        self.clipboard = ClipboardManager(self)
        self.attachments = []  # список кортежей (filepath, filename)
        self.encryption_mode = "none"
        
        self.title("Новое письмо")
        self.geometry("900x720")
        self.minsize(750, 620)
        self.transient(parent)
        self.configure(fg_color=("#f0f0f0", "#1e1e1e"))
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Создание интерфейса"""
        self.grid_rowconfigure(0, weight=0)   # шапка
        self.grid_rowconfigure(1, weight=1)   # тело письма + правая панель
        self.grid_rowconfigure(2, weight=0)   # кнопки
        self.grid_columnconfigure(0, weight=3, minsize=400)
        self.grid_columnconfigure(1, weight=2, minsize=280)
        
        # Строка 0: получатель/тема (слева) и стенография (справа)
        self._create_recipient_panel()      # row=0, col=0
        self._create_steganography_panel()  # row=0, col=1
        
        # Строка 1: тело письма (слева) и комбинированная панель (справа)
        self._create_body_panel()           # row=1, col=0
        
        # Правая панель: шифрование + вложения
        right_panel = ctk.CTkFrame(self, fg_color="transparent")
        right_panel.grid(row=1, column=1, padx=(12, 20), pady=(0, 12), sticky="nsew")
        right_panel.grid_rowconfigure(0, weight=0)  # шифрование
        right_panel.grid_rowconfigure(1, weight=1)  # вложения
        right_panel.grid_columnconfigure(0, weight=1)
        
        self._create_encryption_panel(right_panel)  # row=0 внутри right_panel
        self._create_attachments_panel(right_panel) # row=1 внутри right_panel
        
        # Кнопка отправки
        self._create_send_button()
    
    def _create_recipient_panel(self):
        """Создание панели с получателем и темой"""
        frame = ctk.CTkFrame(self, corner_radius=12, fg_color=Styles.CARD_BG,
                            border_width=1, border_color=Styles.CARD_BORDER)
        frame.grid(row=0, column=0, padx=(20, 12), pady=(20, 12), sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        
        # Кому
        ctk.CTkLabel(frame, text="Кому", font=("Segoe UI", 12, "bold"),
                    text_color=Styles.TEXT_SECONDARY).pack(anchor="w", padx=14, pady=(14, 2))
        self.recipient_entry = self.clipboard.create_entry_with_clipboard(
            frame, placeholder_text="логин получателя", font=Styles.FONT_NORMAL,
            height=38, corner_radius=8, border_width=1, border_color=Styles.CARD_BORDER
        )
        self.recipient_entry.pack(fill="x", padx=14, pady=(2, 14))
        
        # Тема
        ctk.CTkLabel(frame, text="Тема", font=("Segoe UI", 12, "bold"),
                    text_color=Styles.TEXT_SECONDARY).pack(anchor="w", padx=14, pady=(0, 2))
        self.subject_entry = self.clipboard.create_entry_with_clipboard(
            frame, placeholder_text="тема письма", font=Styles.FONT_NORMAL,
            height=38, corner_radius=8, border_width=1, border_color=Styles.CARD_BORDER
        )
        self.subject_entry.pack(fill="x", padx=14, pady=(2, 14))
    
    def _create_steganography_panel(self):
        """Панель стенографии"""
        frame = ctk.CTkFrame(self, corner_radius=12, fg_color=Styles.CARD_BG,
                            border_width=1, border_color=Styles.CARD_BORDER)
        frame.grid(row=0, column=1, padx=(12, 20), pady=(20, 12), sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Стенография", font=("Segoe UI", 14, "bold"),
                    text_color=Styles.TEXT_PRIMARY).pack(anchor="w", padx=14, pady=(14, 8))

        self.steg_switch = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(frame, text="Использовать стенографию",
                    variable=self.steg_switch, font=Styles.FONT_NORMAL,
                    progress_color=Styles.BTN_COLOR,
                    command=self._on_steg_toggle).pack(anchor="w", padx=14, pady=4)

        # Скрытое сообщение
        self.steg_msg_label = ctk.CTkLabel(frame, text="Скрытое сообщение:",
                                        font=("Segoe UI", 12, "bold"),
                                        text_color=Styles.TEXT_SECONDARY)
        self.steg_msg_text = ctk.CTkTextbox(frame, height=60, font=Styles.FONT_MONO,
                                            wrap="word")
        self.clipboard.configure_textbox(self.steg_msg_text)
        self.steg_msg_text.pack_forget()

        # AES-ключ для стенографии
        self.steg_key_label = ctk.CTkLabel(frame, text="AES ключ (64 hex):",
                                        font=("Segoe UI", 12, "bold"),
                                        text_color=Styles.TEXT_SECONDARY)
        self.steg_key_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.steg_key_entry = self.clipboard.create_entry_with_clipboard(
            self.steg_key_frame,
            font=Styles.FONT_MONO, height=30, corner_radius=8,
            border_width=1, border_color=Styles.CARD_BORDER)
        self.steg_key_gen_btn = ctk.CTkButton(self.steg_key_frame, text="Сген.",
                                            width=50, height=30,
                                            command=self._generate_steg_aes_key,
                                            fg_color=Styles.BTN_COLOR,
                                            hover_color=Styles.BTN_HOVER)
        self.steg_key_frame.pack_forget()

        self.steg_gen_btn = ctk.CTkButton(frame, text="Сгенерировать ключ-файл",
                                        command=self._generate_stego_keyfile,
                                        fg_color=Styles.BTN_COLOR,
                                        hover_color=Styles.BTN_HOVER,
                                        font=Styles.FONT_NORMAL, corner_radius=8, height=32)
        self.steg_gen_btn.pack_forget()

        self.steg_key_hex_entry = self.clipboard.create_entry_with_clipboard(
            frame,
            font=Styles.FONT_MONO, height=30, corner_radius=8,
            border_width=1, border_color=Styles.CARD_BORDER
        )
        self.steg_key_hex_entry.configure(state="readonly")
        self.steg_key_hex_entry.pack_forget()
    
    def _create_body_panel(self):
        """Создание панели текста письма"""
        frame = ctk.CTkFrame(self, corner_radius=12, fg_color=Styles.CARD_BG,
                            border_width=1, border_color=Styles.CARD_BORDER)
        frame.grid(row=1, column=0, padx=(20, 12), pady=(0, 12), sticky="nsew")
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(frame, text="Текст письма", font=("Segoe UI", 12, "bold"),
                    text_color=Styles.TEXT_SECONDARY).pack(anchor="w", padx=14, pady=(14, 2))
        
        self.body_text = ctk.CTkTextbox(frame, wrap="word", font=Styles.FONT_MONO,
                                       corner_radius=8, border_width=1,
                                       border_color=Styles.CARD_BORDER)
        self.clipboard.configure_textbox(self.body_text)
        self.body_text.pack(fill="both", expand=True, padx=14, pady=(2, 14))
    
    def _create_encryption_panel(self, parent):
        """Создание панели шифрования внутри parent"""
        frame = ctk.CTkFrame(parent, corner_radius=12, fg_color=Styles.CARD_BG,
                            border_width=1, border_color=Styles.CARD_BORDER)
        frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(frame, text="Шифрование", font=("Segoe UI", 14, "bold"),
                    text_color=Styles.TEXT_PRIMARY).pack(anchor="w", padx=14, pady=(14, 8))
        
        self.mode_var = ctk.StringVar(value="none")
        ctk.CTkRadioButton(frame, text="Нет", variable=self.mode_var, value="none",
                          font=Styles.FONT_NORMAL, fg_color=Styles.BTN_COLOR,
                          hover_color=Styles.BTN_HOVER, border_color=Styles.CARD_BORDER).pack(anchor="w", padx=14, pady=3)
        ctk.CTkRadioButton(frame, text="AES-256", variable=self.mode_var, value="aes",
                          font=Styles.FONT_NORMAL, fg_color=Styles.BTN_COLOR,
                          hover_color=Styles.BTN_HOVER, border_color=Styles.CARD_BORDER).pack(anchor="w", padx=14, pady=3)
        ctk.CTkRadioButton(frame, text="Time-based", variable=self.mode_var, value="time",
                          font=Styles.FONT_NORMAL, fg_color=Styles.BTN_COLOR,
                          hover_color=Styles.BTN_HOVER, border_color=Styles.CARD_BORDER).pack(anchor="w", padx=14, pady=3)
        
        self.key_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.key_frame.pack(fill="x", padx=14, pady=(12, 10))
        
        self.key_label = ctk.CTkLabel(self.key_frame, text="", font=Styles.FONT_SMALL)
        self.key_entry = self.clipboard.create_entry_with_clipboard(
            self.key_frame, font=Styles.FONT_SMALL, height=30,
            corner_radius=8, border_width=1, border_color=Styles.CARD_BORDER
        )
        self.gen_button = ctk.CTkButton(self.key_frame, text="Генерировать", width=100,
                                       fg_color=Styles.BTN_COLOR, hover_color=Styles.BTN_HOVER,
                                       font=("Segoe UI", 10), corner_radius=8)
        
        self.mode_var.trace_add("write", self._on_mode_change)
        self._on_mode_change()
    
    def _create_attachments_panel(self, parent):
        """Панель управления вложениями"""
        frame = ctk.CTkFrame(parent, corner_radius=12, fg_color=Styles.CARD_BG,
                            border_width=1, border_color=Styles.CARD_BORDER)
        frame.grid(row=1, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Вложения", font=("Segoe UI", 12, "bold"),
                    text_color=Styles.TEXT_PRIMARY).pack(anchor="w", padx=14, pady=(10, 5))

        self.attachments_listbox = ctk.CTkTextbox(frame, height=100, font=Styles.FONT_MONO,
                                                wrap="word", state="normal")
        self.attachments_listbox.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self.attachments_listbox.insert("1.0", "Нет вложений")
        self.attachments_listbox.configure(state="disabled")

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=14, pady=(0, 10))
        add_btn = ctk.CTkButton(btn_frame, text="➕ Добавить файлы", command=self._add_attachments,
                                fg_color=Styles.BTN_COLOR, hover_color=Styles.BTN_HOVER)
        add_btn.pack(side="left", padx=(0, 5))
        clear_btn = ctk.CTkButton(btn_frame, text="🗑 Очистить всё", command=self._clear_attachments,
                                fg_color=Styles.BTN_DELETE[0], hover_color=Styles.BTN_DELETE[1])
        clear_btn.pack(side="left")
    
    def _create_send_button(self):
        """Создание кнопки отправки"""
        send_frame = ctk.CTkFrame(self, fg_color="transparent")
        send_frame.grid(row=2, column=0, columnspan=2, padx=20, pady=(0, 20), sticky="ew")
        send_frame.grid_columnconfigure(0, weight=1)
        
        send_btn = ctk.CTkButton(send_frame, text="Отправить", command=self._send,
                                fg_color=Styles.BTN_COLOR, hover_color=Styles.BTN_HOVER,
                                font=("Segoe UI", 14, "bold"), height=44, corner_radius=12)
        send_btn.pack(side="right", padx=0)
    
    # --- Методы для шифрования ---
    def _on_mode_change(self, *args):
        mode = self.mode_var.get()
        self.key_label.pack_forget()
        self.key_entry.pack_forget()
        self.gen_button.pack_forget()
        self.key_entry.delete(0, "end")
        if mode == "aes":
            self.key_label.configure(text="Ключ (base64/hex):")
            self.key_label.pack(anchor="w")
            self.key_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
            self.gen_button.pack(side="right")
            self.gen_button.configure(command=self._generate_aes_key)
        elif mode == "time":
            self.key_label.configure(text="Соль (6-256 символов):")
            self.key_label.pack(anchor="w")
            self.key_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
    
    def _generate_aes_key(self):
        new_key = secrets.token_bytes(32)
        self.key_entry.delete(0, "end")
        self.key_entry.insert(0, base64.b64encode(new_key).decode())
    
    # --- Методы для стенографии ---
    def _on_steg_toggle(self):
        if self.steg_switch.get():
            self.steg_msg_label.pack(anchor="w", padx=14, pady=(8, 2))
            self.steg_msg_text.pack(fill="x", padx=14, pady=(0, 8))
            self.steg_key_label.pack(anchor="w", padx=14, pady=(8, 2))
            self.steg_key_frame.pack(fill="x", padx=14, pady=(0, 8))
            self.steg_key_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
            self.steg_key_gen_btn.pack(side="right")
            self.steg_gen_btn.pack(padx=14, pady=(8, 4))
            self.steg_key_hex_entry.pack(fill="x", padx=14, pady=(0, 8))
        else:
            for w in (self.steg_msg_label, self.steg_msg_text,
                      self.steg_key_label, self.steg_key_frame,
                      self.steg_gen_btn, self.steg_key_hex_entry):
                w.pack_forget()
    
    def _generate_steg_aes_key(self):
        import os
        key = os.urandom(32).hex()
        self.steg_key_entry.delete(0, "end")
        self.steg_key_entry.insert(0, key)
    
    def _generate_stego_keyfile(self):
        from hybrid_steganography import encrypt_and_make_key
        from .dialogs import Dialogs
        secret = self.steg_msg_text.get("1.0", "end-1c").strip()
        carrier = self.body_text.get("1.0", "end-1c").strip()
        aes_hex = self.steg_key_entry.get().strip().replace(" ", "")
        if not secret or not carrier or not aes_hex:
            Dialogs.show_error(self, "Ошибка", "Заполните все поля стенографии")
            return
        try:
            aes_key = bytes.fromhex(aes_hex)
            if len(aes_key) != 32:
                raise ValueError
            keyfile = encrypt_and_make_key(secret, carrier, aes_key)
            hex_key = keyfile.hex()
            self.steg_key_hex_entry.configure(state="normal")
            self.steg_key_hex_entry.delete(0, "end")
            self.steg_key_hex_entry.insert(0, hex_key)
            self.steg_key_hex_entry.configure(state="readonly")
        except Exception as e:
            Dialogs.show_error(self, "Ошибка", str(e))
    
    # --- Методы для вложений ---
    def _add_attachments(self):
        from tkinter import filedialog
        paths = filedialog.askopenfilenames(title="Выберите файлы для вложения")
        for p in paths:
            self.attachments.append((p, os.path.basename(p)))
        self._update_attachments_display()
    
    def _clear_attachments(self):
        self.attachments.clear()
        self._update_attachments_display()
    
    def _update_attachments_display(self):
        self.attachments_listbox.configure(state="normal")
        self.attachments_listbox.delete("1.0", "end")
        if not self.attachments:
            self.attachments_listbox.insert("1.0", "Нет вложений")
        else:
            for i, (path, name) in enumerate(self.attachments, 1):
                self.attachments_listbox.insert("end", f"{i}. {name}\n")
        self.attachments_listbox.configure(state="disabled")
    
    # --- Отправка ---
    def _send(self):
        from .dialogs import Dialogs
        
        recipient = self.recipient_entry.get().strip()
        subject = self.subject_entry.get().strip()
        body = self.body_text.get("1.0", "end-1c").strip()
        
        if not recipient:
            Dialogs.show_error(self, "Ошибка", "Укажите получателя")
            return
        if not subject:
            subject = "(без темы)"
        if not body:
            body = "(пустое тело)"
        
        # --- Стенография ---
        if self.steg_switch.get():
            secret = self.steg_msg_text.get("1.0", "end-1c").strip()
            aes_hex = self.steg_key_entry.get().strip().replace(" ", "")
            if not secret:
                Dialogs.show_error(self, "Ошибка", "Введите скрытое сообщение")
                return
            if not aes_hex:
                Dialogs.show_error(self, "Ошибка", "Введите AES-ключ для стенографии")
                return
            try:
                aes_key = bytes.fromhex(aes_hex)
                if len(aes_key) != 32:
                    raise ValueError
                from hybrid_steganography import encrypt_and_make_key
                keyfile = encrypt_and_make_key(secret, body, aes_key)
                body = body + f"\n[STEGO_KEY]{keyfile.hex()}[/STEGO_KEY]"
            except Exception as e:
                Dialogs.show_error(self, "Ошибка стенографии", str(e))
                return
        
        # --- Шифрование (AES/Time) ---
        mode = self.mode_var.get()

        # Запрещаем вложения для time-based
        if mode == "time" and self.attachments:
            Dialogs.show_error(self, "Ошибка", "Time‑based шифрование не поддерживает вложения.\nИспользуйте AES-256 или отключите шифрование.")
            return


        aes_key_bytes = None
        time_salt = None
        time_bucket = None
        
        if mode == "aes":
            key_str = self.key_entry.get().strip()
            valid, key_bytes, error = Validators.validate_aes_key(key_str)
            if not valid:
                Dialogs.show_error(self, "Ошибка", error)
                return
            aes_key_bytes = key_bytes
        elif mode == "time":
            time_salt = self.key_entry.get().strip()
            valid, error = Validators.validate_time_salt(time_salt)
            if not valid:
                Dialogs.show_error(self, "Ошибка", error)
                return
            time_bucket = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # --- Вложения ---
        attachments_data: List[Tuple[str, bytes]] = []
        for filepath, filename in self.attachments:
            try:
                with open(filepath, "rb") as f:
                    data = f.read()
                attachments_data.append((filename, data))
            except Exception as e:
                Dialogs.show_error(self, "Ошибка", f"Не удалось прочитать файл {filename}: {e}")
                return
        
        # Передаём в main_window
        self.on_send(recipient, subject, body, mode, aes_key_bytes, time_salt, time_bucket, attachments_data)
        self.destroy()