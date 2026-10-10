# utils/clipboard.py
import tkinter as tk
from tkinter import ttk

class ClipboardManager:
    """Управление буфером обмена"""
    
    def __init__(self, root_widget):
        self.root = root_widget
    
    def copy_to_clipboard(self, text: str) -> None:
        """Копирование текста в буфер обмена"""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
    
    def paste_from_clipboard(self, entry_widget) -> None:
        """Вставка из буфера обмена"""
        try:
            text = self.root.clipboard_get()
            entry_widget.insert("insert", text)
        except Exception:
            pass
    
    def create_entry_with_clipboard(self, parent, **kwargs):
        """Создание Entry с поддержкой Ctrl+C/V и правой кнопки"""
        import customtkinter as ctk
        
        entry = ctk.CTkEntry(parent, **kwargs)
        
        # Горячие клавиши
        entry.bind('<Control-v>', lambda e: self.paste_from_clipboard(entry))
        entry.bind('<Control-V>', lambda e: self.paste_from_clipboard(entry))
        entry.bind('<Control-c>', lambda e: self.copy_to_clipboard(entry.get()))
        entry.bind('<Control-C>', lambda e: self.copy_to_clipboard(entry.get()))
        entry.bind('<Control-a>', lambda e: entry.select_range(0, 'end'))
        entry.bind('<Control-A>', lambda e: entry.select_range(0, 'end'))
        
        # Контекстное меню
        menu = tk.Menu(entry, tearoff=0)
        menu.add_command(label="Копировать", command=lambda: self.copy_to_clipboard(entry.get()))
        menu.add_command(label="Вставить", command=lambda: self.paste_from_clipboard(entry))
        menu.add_command(label="Выделить всё", command=lambda: entry.select_range(0, 'end'))
        
        def show_menu(event):
            menu.post(event.x_root, event.y_root)
        
        entry.bind("<Button-3>", show_menu)
        return entry
    
        # utils/clipboard.py (новые методы внутри класса ClipboardManager)

    def configure_textbox(self, textbox):
        """
        Добавляет поддержку Ctrl+C/V/X/A и контекстное меню для CTkTextbox.
        """
        import tkinter as tk

        # Горячие клавиши
        textbox.bind('<Control-v>', lambda e: self._paste_textbox(textbox))
        textbox.bind('<Control-V>', lambda e: self._paste_textbox(textbox))
        textbox.bind('<Control-c>', lambda e: self._copy_textbox(textbox))
        textbox.bind('<Control-C>', lambda e: self._copy_textbox(textbox))
        textbox.bind('<Control-x>', lambda e: self._cut_textbox(textbox))
        textbox.bind('<Control-X>', lambda e: self._cut_textbox(textbox))
        textbox.bind('<Control-a>', lambda e: self._select_all_textbox(textbox))
        textbox.bind('<Control-A>', lambda e: self._select_all_textbox(textbox))

        # Контекстное меню
        menu = tk.Menu(textbox, tearoff=0)
        menu.add_command(label="Вырезать", command=lambda: self._cut_textbox(textbox))
        menu.add_command(label="Копировать", command=lambda: self._copy_textbox(textbox))
        menu.add_command(label="Вставить", command=lambda: self._paste_textbox(textbox))
        menu.add_separator()
        menu.add_command(label="Выделить всё", command=lambda: self._select_all_textbox(textbox))

        def show_menu(event):
            menu.post(event.x_root, event.y_root)
        textbox.bind("<Button-3>", show_menu)

    def _copy_textbox(self, textbox):
        try:
            sel = textbox.get("sel.first", "sel.last")
        except Exception:
            sel = ""
        if sel:
            self.root.clipboard_clear()
            self.root.clipboard_append(sel)

    def _cut_textbox(self, textbox):
        self._copy_textbox(textbox)
        try:
            textbox.delete("sel.first", "sel.last")
        except Exception:
            pass

    def _paste_textbox(self, textbox):
        try:
            text = self.root.clipboard_get()
        except Exception:
            return
        try:
            # Заменяем выделенный текст
            textbox.delete("sel.first", "sel.last")
        except Exception:
            pass
        textbox.insert("insert", text)

    def _select_all_textbox(self, textbox):
        textbox.tag_add("sel", "1.0", "end")