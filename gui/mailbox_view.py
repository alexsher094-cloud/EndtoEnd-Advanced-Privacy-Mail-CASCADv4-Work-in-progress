# gui/mailbox_view.py
import customtkinter as ctk
import os
from typing import List, Optional, Callable
from .styles import Styles
from models.message import Message

class MailboxView(ctk.CTkFrame):
    """Виджет почтового ящика с отображением вложений под телом письма"""

    def __init__(self, parent, username: str, repo, on_message_select: Callable,
                 on_refresh: Callable, on_decrypt: Callable, on_compose: Callable,
                 on_key_manager: Callable, on_delete_all: Callable, on_logout: Callable,
                 on_extract_stego: Callable = None,
                 on_save_single_attachment: Callable = None):
        super().__init__(parent, fg_color="transparent")
        self.parent = parent
        self.username = username
        self.repo = repo                     # сохраняем репозиторий
        self.on_message_select = on_message_select
        self.on_refresh = on_refresh
        self.on_decrypt = on_decrypt
        self.on_compose = on_compose
        self.on_key_manager = on_key_manager
        self.on_delete_all = on_delete_all
        self.on_logout = on_logout
        self.on_extract_stego = on_extract_stego
        self.on_save_single_attachment = on_save_single_attachment

        self.current_filter = "all"
        self.messages: List[Message] = []
        self.selected_message: Optional[Message] = None

        self._create_widgets()
        self._update_connection_status()   # запускаем периодическую проверку

    def _create_widgets(self):
        self.pack(fill="both", expand=True)

        # Верхняя панель
        top_panel = ctk.CTkFrame(self, corner_radius=10,
                                 fg_color=Styles.CARD_BG,
                                 border_width=1, border_color=Styles.CARD_BORDER)
        top_panel.pack(fill="x", padx=5, pady=5)

        user_info = ctk.CTkLabel(top_panel, text=f" {self.username}",
                                 font=Styles.FONT_BOLD)
        user_info.pack(side="left", padx=15, pady=8)

        # Индикатор подключения (справа)
        self.connection_indicator = ctk.CTkLabel(top_panel, text="●", font=("Segoe UI", 16))
        self.connection_indicator.pack(side="right", padx=(0, 10))

        self.logout_btn = ctk.CTkButton(
            top_panel, text="Выйти", width=60, height=30,
            fg_color=Styles.BTN_COLOR, hover_color=Styles.BTN_HOVER,
            command=self.on_logout
        )
        self.logout_btn.pack(side="right", padx=10, pady=5)

        # Основная область
        main_area = ctk.CTkFrame(self, fg_color="transparent")
        main_area.pack(fill="both", expand=True, padx=5, pady=5)

        self._create_message_list_panel(main_area)
        self._create_content_panel(main_area)
        self._create_tools_panel(main_area)

    def _update_connection_status(self):
        """Проверяет соединение с сервером и меняет цвет индикатора"""
        connected = False
        # Для сетевого режима проверяем через ping, если метод есть
        if hasattr(self.repo, 'ping') and callable(self.repo.ping):
            try:
                connected = self.repo.ping()
            except:
                connected = False
        elif hasattr(self.repo, 'sock') and self.repo.sock:
            # Для сетевого режима без ping – проверяем наличие сокета (приблизительно)
            connected = True
        else:
            # Для локального режима – всегда зелёный, но можно скрыть индикатор
            connected = True
            self.connection_indicator.configure(text="")  # скрываем для локального

        color = "green" if connected else "red"
        self.connection_indicator.configure(text_color=color)

        # Планируем следующую проверку через 10 секунд (только если репозиторий сетевой)
        if hasattr(self.repo, 'ping') or hasattr(self.repo, 'sock'):
            self.after(10000, self._update_connection_status)

    # --- остальные методы без изменений ---
    def _create_message_list_panel(self, parent):
        list_container = ctk.CTkFrame(parent, fg_color="transparent")
        list_container.pack(side="left", fill="both", expand=True)

        filter_bar = ctk.CTkFrame(list_container, fg_color="transparent")
        filter_bar.pack(fill="x", padx=1, pady=(0, 5))

        self.btn_all = ctk.CTkButton(
            filter_bar, text="Вся почта",
            command=lambda: self.set_filter("all"),
            fg_color=Styles.BTN_COLOR, hover_color=Styles.BTN_HOVER,
            height=32, font=Styles.FONT_SMALL
        )
        self.btn_all.pack(side="left", padx=2)

        self.btn_inbox = ctk.CTkButton(
            filter_bar, text="Входящие",
            command=lambda: self.set_filter("inbox"),
            fg_color=Styles.BTN_COLOR, hover_color=Styles.BTN_HOVER,
            height=32, font=Styles.FONT_SMALL
        )
        self.btn_inbox.pack(side="left", padx=2)

        self.btn_sent = ctk.CTkButton(
            filter_bar, text="Исходящие",
            command=lambda: self.set_filter("sent"),
            fg_color=Styles.BTN_COLOR, hover_color=Styles.BTN_HOVER,
            height=32, font=Styles.FONT_SMALL
        )
        self.btn_sent.pack(side="left", padx=2)

        self.messages_container = ctk.CTkScrollableFrame(
            list_container, corner_radius=8,
            fg_color=Styles.CARD_BG,
            border_width=1, border_color=Styles.CARD_BORDER
        )
        self.messages_container.pack(fill="both", expand=True, padx=5, pady=5)

    def _create_content_panel(self, parent):
        self.content_panel = ctk.CTkFrame(parent, corner_radius=10,
                                        fg_color=Styles.CARD_BG,
                                        border_width=1, border_color=Styles.CARD_BORDER)
        self.content_panel.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        self.content_panel.grid_rowconfigure(0, weight=0)
        self.content_panel.grid_rowconfigure(1, weight=1)
        self.content_panel.grid_rowconfigure(2, weight=0)
        self.content_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.content_panel, text="Содержимое письма",
                    font=Styles.FONT_BOLD).grid(row=0, column=0, pady=8, padx=5, sticky="w")

        self.message_text = ctk.CTkTextbox(self.content_panel, wrap="word",
                                        font=Styles.FONT_MONO, corner_radius=8)
        self.message_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        # Контейнер для вложений
        self.attachments_container = ctk.CTkFrame(self.content_panel, fg_color="transparent")
        self.attachments_container.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        self.attachments_container.grid_columnconfigure(0, weight=1)

        self.attachments_scroll = ctk.CTkScrollableFrame(
            self.attachments_container, fg_color="transparent",
            border_width=0, height=150
        )
        self.attachments_scroll.grid(row=0, column=0, sticky="nsew")
        self.attachments_scroll.grid_columnconfigure(0, weight=1)

        self.attachments_container.grid_remove()

    def _display_attachments(self, message: Message):
        for widget in self.attachments_scroll.winfo_children():
            widget.destroy()

        if not message.has_attachments():
            self.attachments_container.grid_remove()
            return

        self.attachments_container.grid()

        ctk.CTkLabel(self.attachments_scroll, text="Вложения:",
                     font=Styles.FONT_BOLD, anchor="w").pack(anchor="w", pady=(5, 5))

        for att in message.attachments:
            card = ctk.CTkFrame(self.attachments_scroll, corner_radius=8,
                                border_width=1, border_color=Styles.CARD_BORDER,
                                fg_color=Styles.CARD_BG)
            card.pack(fill="x", pady=3, padx=5)

            inner_frame = ctk.CTkFrame(card, fg_color="transparent")
            inner_frame.pack(fill="x", padx=8, pady=5)

            name = att.get("name", "unknown")
            size = att.get("size", 0)
            size_str = f" ({size // 1024} КБ)" if size > 1024 else f" ({size} байт)" if size else ""

            left_frame = ctk.CTkFrame(inner_frame, fg_color="transparent")
            left_frame.pack(side="left", fill="x", expand=True)

            ctk.CTkLabel(left_frame, text=f"📎 {name}", font=("Segoe UI", 12, "bold"),
                        anchor="w", wraplength=500).pack(anchor="w")
            if size_str:
                ctk.CTkLabel(left_frame, text=size_str, font=Styles.FONT_SMALL,
                            text_color=Styles.TEXT_SECONDARY, anchor="w").pack(anchor="w")

            save_btn = ctk.CTkButton(inner_frame, text="Сохранить", width=80, height=28,
                                    command=lambda a=att: self._save_single_attachment(message, a))
            save_btn.pack(side="right", padx=(5, 0))

    def _save_single_attachment(self, message: Message, attachment: dict):
        from tkinter import filedialog
        from .dialogs import Dialogs

        initial_file = attachment["name"]
        file_path = filedialog.asksaveasfilename(
            title="Сохранить вложение",
            initialfile=initial_file,
            defaultextension=os.path.splitext(initial_file)[1],
            filetypes=[("All files", "*.*")]
        )
        if not file_path:
            return

        if self.on_save_single_attachment:
            self.on_save_single_attachment(message, attachment, file_path)
        else:
            Dialogs.show_error(self, "Ошибка", "Сохранение вложений не настроено")

    def _create_tools_panel(self, parent):
        tools_panel = ctk.CTkFrame(parent, corner_radius=10,
                                   fg_color=Styles.CARD_BG,
                                   border_width=1, border_color=Styles.CARD_BORDER)
        tools_panel.pack(side="right", fill="y", padx=2, pady=2)
        tools_scroll = ctk.CTkScrollableFrame(tools_panel, fg_color="transparent", width=230)
        tools_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        self._add_tool_button(tools_scroll, "Новое письмо", self.on_compose)
        self._add_tool_button(tools_scroll, "Обновить", self.on_refresh)
        self._add_tool_button(tools_scroll, "Дешифровать", self._on_decrypt_click)
        if self.on_extract_stego:
            self._add_tool_button(tools_scroll, "Извлечь скрытое", self._on_extract_stego_click)
        self._add_tool_button(tools_scroll, "Менеджер ключей", self.on_key_manager)
        self._add_tool_button(tools_scroll, "Удалить почту", self._on_delete_click, is_delete=True)

        self._create_auto_refresh_widgets(tools_scroll)

    def _add_tool_button(self, parent, text: str, command, is_delete=False):
        if is_delete:
            btn = ctk.CTkButton(parent, text=text, font=Styles.FONT_NORMAL,
                                fg_color=Styles.BTN_DELETE[0],
                                hover_color=Styles.BTN_DELETE[1],
                                text_color="white", height=40, corner_radius=10)
        else:
            btn = ctk.CTkButton(parent, text=text, font=Styles.FONT_BOLD,
                                fg_color=Styles.BTN_COLOR,
                                hover_color=Styles.BTN_HOVER,
                                height=45, corner_radius=10)
        btn.pack(fill="x", pady=5)
        btn.configure(command=command)
        return btn

    def _create_auto_refresh_widgets(self, parent):
        from config import Config
        auto_frame = ctk.CTkFrame(parent, fg_color="transparent")
        auto_frame.pack(fill="x", pady=10)
        ctk.CTkLabel(auto_frame, text="Автообновление",
                     font=Styles.FONT_BOLD).pack(anchor="w")
        self.auto_refresh_var = ctk.BooleanVar(value=False)
        self.auto_check = ctk.CTkCheckBox(auto_frame, text="Включить",
                                          variable=self.auto_refresh_var,
                                          font=Styles.FONT_SMALL)
        self.auto_check.pack(anchor="w", pady=2)
        interval_frame = ctk.CTkFrame(auto_frame, fg_color="transparent")
        interval_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(interval_frame, text="Интервал (сек):",
                     font=Styles.FONT_SMALL).pack(side="left", padx=5)
        self.interval_combo = ctk.CTkComboBox(
            interval_frame, values=Config.AUTO_REFRESH_INTERVALS,
            width=80, font=Styles.FONT_SMALL
        )
        self.interval_combo.set(str(Config.DEFAULT_AUTO_REFRESH_INTERVAL))
        self.interval_combo.pack(side="left", padx=5)

    def set_filter(self, filter_type: str):
        self.current_filter = filter_type
        active_color = ("#555555", "#aaaaaa")
        for btn, ftype in [(self.btn_all, "all"), (self.btn_inbox, "inbox"), (self.btn_sent, "sent")]:
            btn.configure(fg_color=active_color if ftype == filter_type else Styles.BTN_COLOR)
        self.refresh_display()

    def refresh_display(self):
        for widget in self.messages_container.winfo_children():
            widget.destroy()
        if not self.messages:
            self._show_empty_state()
            return
        filtered = self._filter_messages()
        if not filtered:
            self._show_empty_filter_state()
            return
        for msg in filtered:
            self._create_message_card(msg)
        if filtered:
            self.select_message(filtered[0])

    def _filter_messages(self) -> List[Message]:
        if self.current_filter == "inbox":
            return [m for m in self.messages if m.folder == "inbox"]
        elif self.current_filter == "sent":
            return [m for m in self.messages if m.folder == "sent"]
        return self.messages.copy()

    def _show_empty_state(self):
        info_label = ctk.CTkLabel(self.messages_container, text="Писем нет.",
                                  font=Styles.FONT_NORMAL)
        info_label.pack(pady=20)
        self.message_text.delete("1.0", "end")
        self.message_text.insert("1.0", "Почтовый ящик пуст.")
        self.attachments_container.grid_remove()

    def _show_empty_filter_state(self):
        info_label = ctk.CTkLabel(self.messages_container,
                                  text="Нет писем для данного фильтра.",
                                  font=Styles.FONT_NORMAL)
        info_label.pack(pady=20)
        self.message_text.delete("1.0", "end")
        self.message_text.insert("1.0", "Нет писем, соответствующих фильтру.")
        self.attachments_container.grid_remove()

    def _create_message_card(self, msg: Message):
        card = ctk.CTkFrame(self.messages_container, corner_radius=8,
                            border_width=1, border_color=Styles.CARD_BORDER,
                            fg_color=Styles.CARD_BG)
        card.pack(fill="x", pady=2, padx=3)

        subject_text = msg.display_subject
        if msg.has_attachments():
            subject_text += " Вложение"
        ctk.CTkLabel(card, text=subject_text, font=Styles.FONT_BOLD,
                     anchor="w").pack(anchor="w", padx=8, pady=(4, 0))

        info_text = f"От: {msg.sender} -> {msg.recipient} | {msg.display_date}"
        ctk.CTkLabel(card, text=info_text, font=Styles.FONT_SMALL,
                     text_color=Styles.TEXT_SECONDARY).pack(anchor="w", padx=8)

        preview_text = msg.preview[:50] + "..." if len(msg.preview) > 50 else msg.preview
        ctk.CTkLabel(card, text=preview_text, font=Styles.FONT_SMALL,
                     anchor="w", justify="left").pack(anchor="w", padx=8, pady=(0, 4))

        def on_enter(e, c=card):
            c.configure(fg_color=("#e0e0e0", "#3a3a4e"))

        def on_leave(e, c=card):
            c.configure(fg_color=Styles.CARD_BG)

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

        def make_handler(m=msg):
            return lambda event=None: self.select_message(m)

        handler = make_handler()
        card.bind("<Button-1>", handler)
        for child in card.winfo_children():
            child.bind("<Button-1>", handler)

    def select_message(self, message: Message):
        self.selected_message = message
        self.on_message_select(message)
        self.message_text.delete("1.0", "end")
        self.message_text.insert("1.0", message.body_raw)
        self._display_attachments(message)

    def update_messages(self, messages: List[Message]):
        self.messages = messages
        self.refresh_display()

    def _on_decrypt_click(self):
        if self.selected_message:
            self.on_decrypt(self.selected_message)
        else:
            from .dialogs import Dialogs
            Dialogs.show_warning(self, "Внимание", "Сначала выберите письмо")

    def _on_extract_stego_click(self):
        if self.selected_message and self.selected_message.has_stego:
            if self.on_extract_stego:
                self.on_extract_stego(self.selected_message)
            else:
                from .dialogs import Dialogs
                Dialogs.show_warning(self, "Внимание", "Функция извлечения не настроена")
        else:
            from .dialogs import Dialogs
            Dialogs.show_warning(self, "Внимание", "В выбранном письме нет скрытых данных")

    def _on_delete_click(self):
        self.on_delete_all()

    def get_auto_refresh_settings(self):
        return {
            "enabled": self.auto_refresh_var.get(),
            "interval": int(self.interval_combo.get())
        }