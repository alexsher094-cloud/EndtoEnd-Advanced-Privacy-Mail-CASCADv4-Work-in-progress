# gui/key_manager_view.py
import customtkinter as ctk
import base64
import secrets
from typing import Callable
from .styles import Styles
from encryption.key_storage import KeyStorage
from utils.clipboard import ClipboardManager
from utils.validators import Validators

class KeyManagerView(ctk.CTkToplevel):
    """Окно управления ключами"""
    
    def __init__(self, parent, key_storage: KeyStorage, on_key_update: Callable = None):
        super().__init__(parent)
        self.parent = parent
        self.key_storage = key_storage
        self.on_key_update = on_key_update
        
        self.clipboard = ClipboardManager(self)
        
        self.title("Менеджер ключей")
        self.geometry("700x600")
        self.minsize(600, 500)
        self.transient(parent)

        #################
        #self.grab_set()#  Годжосатору запечатали
        #################
        
        self.configure(fg_color=("#f0f0f0", "#1e1e1e"))
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Создание интерфейса"""
        header = ctk.CTkLabel(self, text="Управление ключами", font=Styles.FONT_TITLE,
                              text_color=Styles.TEXT_PRIMARY)
        header.pack(pady=(20, 10))
        
        self.tabview = ctk.CTkTabview(self, corner_radius=12, fg_color="transparent",
                                      segmented_button_fg_color=("#d0d0d0", "#2a2a2e"),
                                      segmented_button_selected_color=("#909090", "#606060"),
                                      segmented_button_unselected_color=("#e0e0e0", "#3a3a4e"))
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Вкладки
        self._build_aes_tab(self.tabview.add("AES ключи"))
        self._build_time_tab(self.tabview.add("Time-соли"))
        self._build_num_tab(self.tabview.add("Номерные ключи"))
    
    def _build_aes_tab(self, parent):
        """Создание вкладки AES ключей"""
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Список ключей
        self.aes_list = ctk.CTkScrollableFrame(container, height=250, corner_radius=10,
                                               fg_color=Styles.CARD_BG, border_width=1,
                                               border_color=Styles.CARD_BORDER)
        self.aes_list.pack(fill="both", expand=True, padx=5, pady=(0, 15))
        
        # Форма добавления
        form = ctk.CTkFrame(container, corner_radius=10, fg_color="transparent")
        form.pack(fill="x", pady=5)
        form.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(form, text="Имя ключа:", font=Styles.FONT_NORMAL, 
                    anchor="w").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.aes_name = ctk.CTkEntry(form, placeholder_text="например, ключ сервера",
                                     font=Styles.FONT_NORMAL, height=35, corner_radius=8)
        self.aes_name.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        ctk.CTkLabel(form, text="Ключ (base64/hex):", font=Styles.FONT_NORMAL,
                    anchor="w").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.aes_key = self.clipboard.create_entry_with_clipboard(
            form, placeholder_text="32 байта в base64 или hex",
            font=Styles.FONT_NORMAL, height=35, corner_radius=8
        )
        self.aes_key.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        
        btn_frame = ctk.CTkFrame(form, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, pady=15)
        
        ctk.CTkButton(btn_frame, text="Сгенерировать", command=self._gen_aes, width=140,
                     fg_color=Styles.BTN_COLOR, hover_color=Styles.BTN_HOVER,
                     font=Styles.FONT_NORMAL, corner_radius=8).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Добавить", command=self._add_aes, width=120,
                     fg_color=Styles.BTN_COLOR, hover_color=Styles.BTN_HOVER,
                     font=Styles.FONT_NORMAL, corner_radius=8).pack(side="left", padx=5)
        
        self._refresh_aes()
    
    def _gen_aes(self):
        """Генерация AES ключа"""
        key = secrets.token_bytes(32)
        self.aes_key.delete(0, "end")
        self.aes_key.insert(0, base64.b64encode(key).decode())
    
    def _add_aes(self):
        """Добавление AES ключа"""
        from .dialogs import Dialogs
        
        name = self.aes_name.get().strip()
        key_str = self.aes_key.get().strip()
        
        if not name or not key_str:
            Dialogs.show_error(self, "Ошибка", "Введите имя и ключ")
            return
        
        valid, key_bytes, error = Validators.validate_aes_key(key_str)
        if not valid:
            Dialogs.show_error(self, "Ошибка", error)
            return
        
        self.key_storage.add_aes_key(name, key_bytes)
        self._refresh_aes()
        self.aes_name.delete(0, "end")
        self.aes_key.delete(0, "end")
        
        if self.on_key_update:
            self.on_key_update()
    
    def _refresh_aes(self):
        """Обновление списка AES ключей"""
        for w in self.aes_list.winfo_children():
            w.destroy()
        
        keys = self.key_storage.get_all_aes_keys()
        if not keys:
            empty = ctk.CTkLabel(self.aes_list, text="Нет добавленных AES ключей",
                                 text_color="gray", font=("Segoe UI", 12, "italic"))
            empty.pack(pady=30)
            return
        
        for name, key in keys.items():
            self._create_aes_card(name, key)
    
    def _create_aes_card(self, name: str, key: bytes):
        """Создание карточки AES ключа"""
        card = ctk.CTkFrame(self.aes_list, corner_radius=8, fg_color="transparent",
                           border_width=1, border_color=Styles.CARD_BORDER)
        card.pack(fill="x", pady=3, padx=5)
        
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=10, pady=5)
        
        short_key = base64.b64encode(key).decode()[:24] + "..."
        ctk.CTkLabel(info, text=name, font=("Segoe UI", 13, "bold"),
                    anchor="w").pack(anchor="w")
        ctk.CTkLabel(info, text=short_key, font=("Consolas", 11),
                    text_color="gray", anchor="w").pack(anchor="w")
        
        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.pack(side="right", padx=5, pady=5)
        
        ctk.CTkButton(btns, text="Копировать", width=80,
                     command=lambda k=key: self._copy_key(k),
                     fg_color=Styles.BTN_COLOR, hover_color=Styles.BTN_HOVER,
                     font=("Segoe UI", 11), corner_radius=6).pack(side="left", padx=3)
        ctk.CTkButton(btns, text="Удалить", width=70,
                     command=lambda n=name: self._del_aes(n),
                     fg_color=Styles.BTN_DELETE[0], hover_color=Styles.BTN_DELETE[1],
                     font=("Segoe UI", 11), corner_radius=6).pack(side="left", padx=3)
    
    def _del_aes(self, name: str):
        """Удаление AES ключа"""
        self.key_storage.delete_aes_key(name)
        self._refresh_aes()
        
        if self.on_key_update:
            self.on_key_update()
    
    def _copy_key(self, key_bytes: bytes):
        """Копирование ключа"""
        b64 = base64.b64encode(key_bytes).decode()
        self.clipboard.copy_to_clipboard(b64)
        from .dialogs import Dialogs
        Dialogs.show_info(self, "Скопировано", "AES-ключ скопирован в буфер обмена")
    
    def _build_time_tab(self, parent):
        """Создание вкладки Time-солей"""
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.time_list = ctk.CTkScrollableFrame(container, height=250, corner_radius=10,
                                                fg_color=Styles.CARD_BG, border_width=1,
                                                border_color=Styles.CARD_BORDER)
        self.time_list.pack(fill="both", expand=True, padx=5, pady=(0, 15))
        
        form = ctk.CTkFrame(container, corner_radius=10, fg_color="transparent")
        form.pack(fill="x", pady=5)
        form.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(form, text="Имя соли:", font=Styles.FONT_NORMAL,
                    anchor="w").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.time_name = ctk.CTkEntry(form, placeholder_text="например, salt_2024",
                                      font=Styles.FONT_NORMAL, height=35, corner_radius=8)
        self.time_name.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        ctk.CTkLabel(form, text="Соль:", font=Styles.FONT_NORMAL,
                    anchor="w").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.time_salt = self.clipboard.create_entry_with_clipboard(
            form, placeholder_text="6-256 символов",
            font=Styles.FONT_NORMAL, height=35, corner_radius=8
        )
        self.time_salt.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        
        btn_frame = ctk.CTkFrame(form, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, pady=15)
        
        ctk.CTkButton(btn_frame, text="Сгенерировать", command=self._gen_salt, width=140,
                     fg_color=Styles.BTN_COLOR, hover_color=Styles.BTN_HOVER,
                     font=Styles.FONT_NORMAL, corner_radius=8).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Добавить", command=self._add_salt, width=120,
                     fg_color=Styles.BTN_COLOR, hover_color=Styles.BTN_HOVER,
                     font=Styles.FONT_NORMAL, corner_radius=8).pack(side="left", padx=5)
        
        self._refresh_time()
    
    def _gen_salt(self):
        """Генерация соли"""
        import secrets
        self.time_salt.delete(0, "end")
        self.time_salt.insert(0, secrets.token_urlsafe(16))
    
    def _add_salt(self):
        """Добавление соли"""
        from .dialogs import Dialogs
        
        name = self.time_name.get().strip()
        salt = self.time_salt.get().strip()
        
        if not name or not salt:
            Dialogs.show_error(self, "Ошибка", "Введите имя и соль")
            return
        
        valid, error = Validators.validate_time_salt(salt)
        if not valid:
            Dialogs.show_error(self, "Ошибка", error)
            return
        
        self.key_storage.add_time_salt(name, salt)
        self._refresh_time()
        self.time_name.delete(0, "end")
        self.time_salt.delete(0, "end")
        
        if self.on_key_update:
            self.on_key_update()
    
    def _refresh_time(self):
        """Обновление списка солей"""
        for w in self.time_list.winfo_children():
            w.destroy()
        
        salts = self.key_storage.get_all_time_salts()
        if not salts:
            empty = ctk.CTkLabel(self.time_list, text="Нет сохранённых солей",
                                 text_color="gray", font=("Segoe UI", 12, "italic"))
            empty.pack(pady=30)
            return
        
        for name, salt in salts.items():
            self._create_time_card(name, salt)
    
    def _create_time_card(self, name: str, salt: str):
        """Создание карточки соли"""
        card = ctk.CTkFrame(self.time_list, corner_radius=8, fg_color="transparent",
                           border_width=1, border_color=Styles.CARD_BORDER)
        card.pack(fill="x", pady=3, padx=5)
        
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=10, pady=5)
        
        short_salt = salt[:20] + "..." if len(salt) > 20 else salt
        ctk.CTkLabel(info, text=name, font=("Segoe UI", 13, "bold"),
                    anchor="w").pack(anchor="w")
        ctk.CTkLabel(info, text=short_salt, font=("Consolas", 11),
                    text_color="gray", anchor="w").pack(anchor="w")
        
        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.pack(side="right", padx=5, pady=5)
        
        ctk.CTkButton(btns, text="Копировать", width=80,
                     command=lambda s=salt: self.clipboard.copy_to_clipboard(s),
                     fg_color=Styles.BTN_COLOR, hover_color=Styles.BTN_HOVER,
                     font=("Segoe UI", 11), corner_radius=6).pack(side="left", padx=3)
        ctk.CTkButton(btns, text="Удалить", width=70,
                     command=lambda n=name: self._del_time(n),
                     fg_color=Styles.BTN_DELETE[0], hover_color=Styles.BTN_DELETE[1],
                     font=("Segoe UI", 11), corner_radius=6).pack(side="left", padx=3)
    
    def _del_time(self, name: str):
        """Удаление соли"""
        self.key_storage.delete_time_salt(name)
        self._refresh_time()
        
        if self.on_key_update:
            self.on_key_update()
    
    def _build_num_tab(self, parent):
        """Создание вкладки номерных ключей"""
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(container, text="Номерные ключи (из номерной радиостанции)",
                    font=Styles.FONT_HEADER).pack(anchor="w", pady=(5, 10))
        
        self.num_list_frame = ctk.CTkScrollableFrame(container, height=250, corner_radius=10,
                                                     fg_color=Styles.CARD_BG, border_width=1,
                                                     border_color=Styles.CARD_BORDER)
        self.num_list_frame.pack(fill="both", expand=True, padx=5, pady=(0, 15))
        
        add_frame = ctk.CTkFrame(container, corner_radius=10, fg_color="transparent")
        add_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(add_frame, text="Новый ключ:", font=Styles.FONT_NORMAL).pack(side="left", padx=10)
        self.new_num_entry = self.clipboard.create_entry_with_clipboard(
            add_frame, width=200, placeholder_text="827 529 145",
            font=Styles.FONT_NORMAL, height=35, corner_radius=8
        )
        self.new_num_entry.pack(side="left", padx=5)
        
        ctk.CTkButton(add_frame, text="Добавить", command=self._add_num_key,
                     fg_color=Styles.BTN_COLOR, hover_color=Styles.BTN_HOVER,
                     font=Styles.FONT_NORMAL, corner_radius=8).pack(side="left", padx=5)
        ctk.CTkButton(add_frame, text="Импорт из аудио", command=self._import_audio,
                     fg_color=Styles.BTN_COLOR, hover_color=Styles.BTN_HOVER,
                     font=Styles.FONT_NORMAL, corner_radius=8).pack(side="left", padx=5)
        
        self._refresh_num_keys()
    
    def _add_num_key(self):
        """Добавление номерного ключа"""
        from .dialogs import Dialogs
        
        key = self.new_num_entry.get().strip()
        if not key:
            Dialogs.show_error(self, "Ошибка", "Введите номерной ключ")
            return
        
        self.key_storage.add_num_key(key)
        self._refresh_num_keys()
        self.new_num_entry.delete(0, "end")
        Dialogs.show_info(self, "Успех", "Ключ добавлен")
    
    def _import_audio(self):
        """Импорт из аудио"""
        from .dialogs import Dialogs
        Dialogs.show_info(self, "В разработке", "Функция импорта из аудио находится в разработке.")
    
    def _refresh_num_keys(self):
        """Обновление списка номерных ключей"""
        for w in self.num_list_frame.winfo_children():
            w.destroy()
        
        keys = self.key_storage.get_all_num_keys()
        if not keys:
            empty = ctk.CTkLabel(self.num_list_frame, text="Нет сохранённых номерных ключей",
                                 text_color="gray", font=("Segoe UI", 12, "italic"))
            empty.pack(pady=30)
            return
        
        for idx, key in enumerate(keys):
            card = ctk.CTkFrame(self.num_list_frame, corner_radius=8, fg_color="transparent",
                               border_width=1, border_color=Styles.CARD_BORDER)
            card.pack(fill="x", pady=3, padx=5)
            
            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=10, pady=5)
            
            ctk.CTkLabel(info, text=f"{idx+1}. {key}", font=("Consolas", 13, "bold"),
                        anchor="w").pack(anchor="w")
            
            btns = ctk.CTkFrame(card, fg_color="transparent")
            btns.pack(side="right", padx=5, pady=5)
            
            ctk.CTkButton(btns, text="Копировать", width=80,
                         command=lambda k=key: self.clipboard.copy_to_clipboard(k),
                         fg_color=Styles.BTN_COLOR, hover_color=Styles.BTN_HOVER,
                         font=("Segoe UI", 11), corner_radius=6).pack(side="left", padx=3)
            ctk.CTkButton(btns, text="Удалить", width=70,
                         command=lambda i=idx: self._del_num_key(i),
                         fg_color=Styles.BTN_DELETE[0], hover_color=Styles.BTN_DELETE[1],
                         font=("Segoe UI", 11), corner_radius=6).pack(side="left", padx=3)
    
    def _del_num_key(self, idx: int):
        """Удаление номерного ключа"""
        self.key_storage.delete_num_key(idx)
        self._refresh_num_keys()