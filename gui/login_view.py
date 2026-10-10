# gui/login_view.py
import customtkinter as ctk
from tkinter import filedialog
from .styles import Styles
from utils.validators import Validators
from utils.clipboard import ClipboardManager

class LoginView(ctk.CTkFrame):
    """Экран входа и регистрации с выбором локального или сетевого режима"""

    def __init__(self, parent, on_login_success: callable, on_server_change: callable = None):
        super().__init__(parent, fg_color="transparent")
        self.parent = parent
        self.on_login_success = on_login_success
        self.on_server_change = on_server_change

        self.clipboard = ClipboardManager(self)
        self._create_widgets()

    def _create_widgets(self):
        self.pack(fill="both", expand=True)

        # Карточка с двумя колонками
        card = ctk.CTkFrame(
            self, corner_radius=20, border_width=2,
            border_color=Styles.CARD_BORDER, fg_color=Styles.CARD_BG
        )
        card.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.9, relheight=0.9)
        card.grid_columnconfigure(0, weight=1)  # левая колонка
        card.grid_columnconfigure(1, weight=1)  # правая колонка
        card.grid_rowconfigure(0, weight=1)

        # --- ЛЕВАЯ КОЛОНКА: логин/пароль и кнопки ---
        left_frame = ctk.CTkFrame(card, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(30, 15), pady=30)
        left_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left_frame, text="Вход в систему", font=Styles.FONT_TITLE,
                    text_color=Styles.TEXT_PRIMARY).pack(anchor="center", pady=(0, 30))

        # Логин
        ctk.CTkLabel(left_frame, text="Логин:", font=Styles.FONT_NORMAL,
                    text_color=Styles.TEXT_PRIMARY).pack(anchor="w", pady=(10, 5))
        self.login_entry = self.clipboard.create_entry_with_clipboard(
            left_frame, placeholder_text="Введите логин",
            font=Styles.FONT_NORMAL, height=40, corner_radius=12
        )
        self.login_entry.pack(fill="x", pady=(0, 5))

        # Пароль
        ctk.CTkLabel(left_frame, text="Пароль:", font=Styles.FONT_NORMAL,
                    text_color=Styles.TEXT_PRIMARY).pack(anchor="w", pady=(10, 5))
        self.password_entry = self.clipboard.create_entry_with_clipboard(
            left_frame, placeholder_text="Введите пароль", show="*",
            font=Styles.FONT_NORMAL, height=40, corner_radius=12
        )
        self.password_entry.pack(fill="x", pady=(0, 5))

        # Кнопки
        btn_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=25)
        self.login_btn = ctk.CTkButton(
            btn_frame, text="Войти", font=Styles.FONT_BOLD,
            height=40, corner_radius=15, command=self._on_login
        )
        self.login_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.register_btn = ctk.CTkButton(
            btn_frame, text="Регистрация", font=Styles.FONT_BOLD,
            height=40, corner_radius=15, command=self._on_register
        )
        self.register_btn.pack(side="right", fill="x", expand=True, padx=(5, 0))

        self.status_label = ctk.CTkLabel(left_frame, text="", font=Styles.FONT_SMALL,
                                        text_color="gray")
        self.status_label.pack(pady=(10, 0))

        # --- ПРАВАЯ КОЛОНКА: режим работы и параметры ---
        right_frame = ctk.CTkFrame(card, fg_color="transparent")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(15, 30), pady=30)
        right_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right_frame, text="Режим работы", font=Styles.FONT_HEADER,
                    text_color=Styles.TEXT_PRIMARY).pack(anchor="w", pady=(0, 15))

        self.mode_var = ctk.StringVar(value="local")
        self.local_radio = ctk.CTkRadioButton(
            right_frame, text="Локальный (папка на компьютере)",
            variable=self.mode_var, value="local", command=self._on_mode_change
        )
        self.local_radio.pack(anchor="w", padx=20, pady=3)
        self.network_radio = ctk.CTkRadioButton(
            right_frame, text="Сетевой (подключение к серверу)",
            variable=self.mode_var, value="network", command=self._on_mode_change
        )
        self.network_radio.pack(anchor="w", padx=20, pady=3)

        # Динамическая панель параметров
        self.params_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        self.params_frame.pack(fill="both", expand=True, pady=(20, 0))

        # Заполняем поля для начального режима
        self._on_mode_change()

    def _on_mode_change(self):
        """Очищает панель параметров и создаёт нужные поля в зависимости от режима"""
        for widget in self.params_frame.winfo_children():
            widget.destroy()

        if self.mode_var.get() == "local":
            self._create_local_fields()
        else:
            self._create_network_fields()

    def _create_local_fields(self):
        """Поля для локального режима: выбор папки"""
        ctk.CTkLabel(self.params_frame, text="Папка с данными:",
                    font=Styles.FONT_NORMAL).pack(anchor="w", pady=(0, 2))

        path_frame = ctk.CTkFrame(self.params_frame, fg_color="transparent")
        path_frame.pack(fill="x")

        self.local_path_var = ctk.StringVar(value="./server_data")
        self.local_path_entry = ctk.CTkEntry(
            path_frame, textvariable=self.local_path_var,
            font=Styles.FONT_NORMAL, height=40, corner_radius=12
        )
        self.local_path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        browse_btn = ctk.CTkButton(
            path_frame, text="Обзор", width=100, height=40,
            command=self._browse_local_folder
        )
        browse_btn.pack(side="right")

        ctk.CTkLabel(self.params_frame,
                    text="Укажите папку, где хранятся почтовые данные.\n"
                         "Если папка пуста, при регистрации будет создана новая структура.",
                    font=Styles.FONT_SMALL, text_color=Styles.TEXT_SECONDARY,
                    wraplength=400).pack(anchor="w", pady=(8, 0))

    def _create_network_fields(self):
        """Поля для сетевого режима: сервер, порт, TLS"""
        # Сервер
        ctk.CTkLabel(self.params_frame, text="Сервер (IP или домен):",
                    font=Styles.FONT_NORMAL).pack(anchor="w", pady=(0, 2))
        self.server_entry = self.clipboard.create_entry_with_clipboard(
            self.params_frame, placeholder_text="например, mail.example.com или 192.168.1.100",
            font=Styles.FONT_NORMAL, height=40, corner_radius=12
        )
        self.server_entry.pack(fill="x", pady=(0, 8))

        # Порт
        ctk.CTkLabel(self.params_frame, text="Порт:",
                    font=Styles.FONT_NORMAL).pack(anchor="w", pady=(0, 2))
        self.port_entry = self.clipboard.create_entry_with_clipboard(
            self.params_frame, placeholder_text="443",
            font=Styles.FONT_NORMAL, height=40, corner_radius=12
        )
        self.port_entry.insert(0, "443")
        self.port_entry.pack(fill="x", pady=(0, 8))

        # TLS/SSL
        self.tls_var = ctk.BooleanVar(value=True)
        self.tls_check = ctk.CTkCheckBox(
            self.params_frame, text="Использовать TLS/SSL (рекомендуется)",
            variable=self.tls_var, font=Styles.FONT_NORMAL
        )
        self.tls_check.pack(anchor="w", pady=(0, 5))

        ctk.CTkLabel(self.params_frame,
                    text="Подключение к серверу EAPM. Пароль передаётся в зашифрованном виде.",
                    font=Styles.FONT_SMALL, text_color=Styles.TEXT_SECONDARY,
                    wraplength=400).pack(anchor="w", pady=(5, 0))

    def _browse_local_folder(self):
        """Выбор папки для локального режима"""
        new_path = filedialog.askdirectory(title="Выберите папку для хранения почтовых данных")
        if new_path:
            self.local_path_var.set(new_path)

    def _get_storage_params(self):
        """Возвращает словарь с параметрами хранилища на основе выбранного режима"""
        if self.mode_var.get() == "local":
            return {
                "mode": "local",
                "path": self.local_path_var.get().strip()
            }
        else:
            server = self.server_entry.get().strip()
            port_str = self.port_entry.get().strip()
            # Валидация будет в обработчике, но здесь можем сразу проверить числовой порт
            try:
                port = int(port_str) if port_str else 443
            except ValueError:
                port = 443
            return {
                "mode": "network",
                "server": server,
                "port": port,
                "tls": self.tls_var.get()
            }

    def _on_login(self):
        """Обработка входа"""
        login = self.login_entry.get().strip()
        password = self.password_entry.get()
        params = self._get_storage_params()

        # Базовая валидация логина/пароля
        valid_login, login_error = Validators.validate_login(login)
        if not valid_login:
            self._show_status(login_error, "red")
            return
        valid_pass, pass_error = Validators.validate_password(password)
        if not valid_pass:
            self._show_status(pass_error, "red")
            return

        # Специфичная валидация для режимов
        if params["mode"] == "local":
            if not params["path"]:
                self._show_status("Укажите папку для данных", "red")
                return
        else:  # network
            if not params["server"]:
                self._show_status("Укажите адрес сервера", "red")
                return
            # порт уже преобразован в int

        # Передаём управление в MainWindow
        if self.on_login_success:
            self.on_login_success(login, password, params, is_register=False)

    def _on_register(self):
        """Обработка регистрации"""
        login = self.login_entry.get().strip()
        password = self.password_entry.get()
        params = self._get_storage_params()

        valid_login, login_error = Validators.validate_login(login)
        if not valid_login:
            self._show_status(login_error, "red")
            return
        valid_pass, pass_error = Validators.validate_password(password)
        if not valid_pass:
            self._show_status(pass_error, "red")
            return

        if params["mode"] == "local":
            if not params["path"]:
                self._show_status("Укажите папку для данных", "red")
                return
        else:
            if not params["server"]:
                self._show_status("Укажите адрес сервера", "red")
                return

        if self.on_login_success:
            self.on_login_success(login, password, params, is_register=True)

    def _show_status(self, message: str, color: str):
        self.status_label.configure(text=message, text_color=color)
        self.after(3000, lambda: self.status_label.configure(text=""))

    def clear(self):
        self.login_entry.delete(0, "end")
        self.password_entry.delete(0, "end")
        self.status_label.configure(text="")