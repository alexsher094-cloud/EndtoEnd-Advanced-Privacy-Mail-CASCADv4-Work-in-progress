# gui/dialogs.py
import customtkinter as ctk
from typing import Optional, Callable, Tuple
from .styles import Styles

class Dialogs:
    """Общие диалоговые окна"""
    
    @staticmethod
    def show_error(parent, title: str, message: str) -> None:
        """Показать ошибку"""
        ctk.CTkInputDialog
        from tkinter import messagebox
        messagebox.showerror(title, message)
    
    @staticmethod
    def show_info(parent, title: str, message: str) -> None:
        """Показать информационное сообщение"""
        from tkinter import messagebox
        messagebox.showinfo(title, message)
    
    @staticmethod
    def show_warning(parent, title: str, message: str) -> None:
        """Показать предупреждение"""
        from tkinter import messagebox
        messagebox.showwarning(title, message)
    
    @staticmethod
    def ask_yes_no(parent, title: str, message: str) -> bool:
        """Спросить Да/Нет"""
        from tkinter import messagebox
        return messagebox.askyesno(title, message)
    
    @staticmethod
    def input_dialog(parent, title: str, prompt: str, 
                     initial_value: str = "") -> Optional[str]:
        """Диалог ввода текста"""
        dialog = ctk.CTkInputDialog(text=prompt, title=title)
        return dialog.get_input()
    
    @staticmethod
    def key_input_dialog(parent, title: str, prompt: str, 
                         is_aes: bool = True) -> Tuple[bool, Optional[bytes], Optional[str]]:
        """Диалог ввода ключа"""
        dialog = ctk.CTkToplevel(parent)
        dialog.title(title)
        dialog.geometry("450x200")
        dialog.transient(parent)
        dialog.grab_set()
        
        result = [False, None, None]  # success, key_bytes, salt
        
        ctk.CTkLabel(dialog, text=prompt, font=Styles.FONT_NORMAL).pack(pady=15, padx=20)
        
        from utils.clipboard import ClipboardManager
        clipboard = ClipboardManager(dialog)
        entry = clipboard.create_entry_with_clipboard(dialog, width=350, font=Styles.FONT_MONO)
        entry.pack(pady=10, padx=20)
        
        def on_ok():
            value = entry.get().strip()
            if is_aes:
                from utils.validators import Validators
                valid, key_bytes, error = Validators.validate_aes_key(value)
                if valid:
                    result[0] = True
                    result[1] = key_bytes
                    dialog.destroy()
                else:
                    Dialogs.show_error(dialog, "Ошибка", error)
            else:
                result[0] = True
                result[2] = value
                dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=15)
        
        ctk.CTkButton(btn_frame, text="OK", command=on_ok, 
                     fg_color=Styles.BTN_COLOR, hover_color=Styles.BTN_HOVER,
                     width=100).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Отмена", command=on_cancel,
                     fg_color=Styles.BTN_COLOR, hover_color=Styles.BTN_HOVER,
                     width=100).pack(side="left", padx=10)
        
        parent.wait_window(dialog)
        return result[0], result[1], result[2]