# gui/main_window.py
import customtkinter as ctk
import datetime
import os
from typing import Optional, List, Tuple
from .styles import Styles
from .login_view import LoginView
from .mailbox_view import MailboxView
from .compose_view import ComposeView
from .key_manager_view import KeyManagerView
from .dialogs import Dialogs
from encryption.key_storage import KeyStorage
from models.message import Message
from .decryptor_dialog import DecryptorDialog
from storage.local_file_repo import LocalFileRepository
from storage.network_repo import NetworkRepository


class MainWindow(ctk.CTk):
    """Главное окно приложения, поддерживает локальный и сетевой режимы."""

    def __init__(self):
        super().__init__()

        Styles.configure_ctk()

        self.title("EAPM - КАСКАД")
        self.geometry("1200x650")
        self.minsize(900, 550)

        # Репозиторий (локальный или сетевой)
        self.repo = None
        self.key_storage = None
        self.current_user = None
        self.auto_refresh_job_id = None

        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.show_login_screen()

    def show_login_screen(self):
        """Показать экран входа"""
        if hasattr(self, 'mailbox_view') and self.mailbox_view:
            self.mailbox_view.destroy()
        self.login_view = LoginView(
            self.main_frame,
            on_login_success=self._handle_login,
            on_server_change=self._change_server
        )

    def _handle_login(self, login: str, password: str, params: dict, is_register: bool = False):
        """Обработка входа или регистрации (локальный или сетевой режим)"""
        mode = params.get("mode")

        if mode == "local":
            server_path = params.get("path")
            if not server_path:
                Dialogs.show_error(self, "Ошибка", "Не указана папка для данных")
                return
            server_path = os.path.abspath(server_path)
            self.repo = LocalFileRepository(server_path)

            if is_register:
                success, msg = self.repo.register_user(login, password)
                if success:
                    Dialogs.show_info(self, "Успех", msg)
                    success, msg = self.repo.authenticate(login, password)
                else:
                    Dialogs.show_error(self, "Ошибка регистрации", msg)
                    return
            else:
                success, msg = self.repo.authenticate(login, password)

            if success:
                self.current_user = login
                self.key_storage = KeyStorage()
                self.show_mailbox_screen()
            else:
                Dialogs.show_error(self, "Ошибка входа", msg)

        elif mode == "network":
            server = params.get("server")
            port = params.get("port")
            use_tls = params.get("tls", True)
            if not server:
                Dialogs.show_error(self, "Ошибка", "Не указан сервер")
                return

            try:
                self.repo = NetworkRepository(server, port, use_tls)
            except Exception as e:
                Dialogs.show_error(self, "Ошибка подключения", str(e))
                return

            if is_register:
                success, msg = self.repo.register_user(login, password)
                if success:
                    Dialogs.show_info(self, "Успех", msg)
                    success, msg = self.repo.authenticate(login, password)
                else:
                    Dialogs.show_error(self, "Ошибка регистрации", msg)
                    return
            else:
                success, msg = self.repo.authenticate(login, password)

            if success:
                self.current_user = login
                self.key_storage = KeyStorage()
                self.show_mailbox_screen()
            else:
                Dialogs.show_error(self, "Ошибка входа", msg)
        else:
            Dialogs.show_error(self, "Ошибка", "Неизвестный режим работы")

    def _change_server(self, new_path: str):
        """Смена сервера (очистка состояния)"""
        if self.current_user:
            self.current_user = None
            if self.key_storage:
                self.key_storage.clear()
                self.key_storage = None
        if self.repo and hasattr(self.repo, 'close'):
            self.repo.close()
        self.repo = None

    def show_mailbox_screen(self):
        """Показать экран почтового ящика"""
        if hasattr(self, 'login_view') and self.login_view:
            self.login_view.destroy()

        self.mailbox_view = MailboxView(
            self.main_frame,
            username=self.current_user,
            repo=self.repo,                     # <-- ПЕРЕДАЁМ РЕПОЗИТОРИЙ
            on_message_select=self._show_message,
            on_refresh=self.refresh_messages,
            on_decrypt=self.decrypt_message,
            on_extract_stego=self.decrypt_stego_message,
            on_compose=self.compose_message,
            on_key_manager=self.open_key_manager,
            on_delete_all=self.delete_all_messages,
            on_logout=self.logout,
            on_save_single_attachment=self._save_single_attachment
        )

        self.refresh_messages()
        self._schedule_auto_refresh()

    def _show_message(self, message: Message):
        """Отображение выбранного сообщения и пометка прочитанным (если нужно)"""
        # Для сетевого режима необходимо получить полное тело и вложения
        if hasattr(self.repo, 'get_full_message') and callable(self.repo.get_full_message):
            full = self.repo.get_full_message(message)
            if full:
                message.body_raw = full.body_raw
                message.attachments = full.attachments
                message.is_read = full.is_read
                if hasattr(self, 'mailbox_view'):
                    self.mailbox_view.selected_message = message

        # Пометка прочитанным
        if message.folder == "inbox" and not message.is_read:
            if hasattr(self.repo, 'mark_message_as_read'):
                self.repo.mark_message_as_read(message)
                message.is_read = True
            elif hasattr(self.repo, 'mark_as_read'):
                self.repo.mark_as_read(self.current_user, message.filename)
                message.is_read = True

    def refresh_messages(self):
        """Обновление списка сообщений"""
        if not self.repo or not self.current_user:
            return
        messages = self.repo.get_messages_list(self.current_user)
        if hasattr(self, 'mailbox_view') and self.mailbox_view:
            self.mailbox_view.update_messages(messages)

    def compose_message(self):
        """Создание нового письма"""
        if not self.current_user:
            return
        ComposeView(self, self.current_user, self._send_message)

    def _send_message(self, recipient: str, subject: str, body: str,
                      mode: str, aes_key: Optional[bytes],
                      time_salt: Optional[str], time_bucket: Optional[str],
                      attachments: Optional[List[Tuple[str, bytes]]] = None):
        """Отправка сообщения (с вложениями)"""
        if not self.repo:
            return
        encryption_mode = mode if mode != "none" else None
        success, msg = self.repo.send_message(
            sender=self.current_user,
            recipient=recipient,
            subject=subject,
            body=body,
            encryption_mode=encryption_mode,
            aes_key=aes_key,
            time_salt=time_salt,
            time_bucket=time_bucket,
            attachments=attachments
        )
        if success:
            Dialogs.show_info(self, "Успех", msg)
            self.refresh_messages()
        else:
            Dialogs.show_error(self, "Ошибка", msg)

    def decrypt_message(self, message: Message):
        """Открыть интерактивный дешифратор"""
        if not self.repo:
            return
        DecryptorDialog(self, message, self.repo)

    def decrypt_stego_message(self, message: Message):
        """Извлечение скрытого сообщения из стего-письма"""
        if not message.has_stego:
            Dialogs.show_info(self, "Информация", "В этом письме нет скрытого сообщения")
            return

        success, aes_key, _ = Dialogs.key_input_dialog(
            self, "Стеганография", "Введите AES ключ (64 hex символа):", is_aes=True
        )
        if not success or not aes_key:
            return

        try:
            key_hex = message.get_stego_key_hex()
            key_bytes = bytes.fromhex(key_hex)
            carrier = message.clean_body
            from hybrid_steganography import recover_from_key
            secret = recover_from_key(key_bytes, carrier, aes_key)
            Dialogs.show_info(self, "Скрытое сообщение", secret)
            if hasattr(self, 'mailbox_view'):
                self.mailbox_view.message_text.delete("1.0", "end")
                self.mailbox_view.message_text.insert("1.0", secret)
        except Exception as e:
            Dialogs.show_error(self, "Ошибка", f"Не удалось извлечь сообщение: {e}")

    def open_key_manager(self):
        """Открытие менеджера ключей"""
        if not self.key_storage:
            return
        KeyManagerView(self, self.key_storage, self.refresh_messages)

    def delete_all_messages(self):
        """Удаление всех сообщений пользователя"""
        result = Dialogs.ask_yes_no(
            self, "Подтверждение",
            "Вы уверены, что хотите удалить ВСЕ письма?\nЭто действие необратимо."
        )
        if not result:
            return

        delete_account = Dialogs.ask_yes_no(
            self, "Удаление аккаунта",
            "Также удалить аккаунт (логин и все данные)?"
        )

        if hasattr(self.repo, 'delete_all_messages'):
            self.repo.delete_all_messages(self.current_user)

        if delete_account:
            if hasattr(self.repo, 'delete_user'):
                self.repo.delete_user(self.current_user)
            Dialogs.show_info(self, "Аккаунт удалён",
                              f"Ваш аккаунт '{self.current_user}' полностью удалён.")
            self.logout()
        else:
            self.refresh_messages()
            Dialogs.show_info(self, "Успех", "Все письма удалены.\nВаш аккаунт сохранён.")

    def logout(self):
        """Выход из аккаунта"""
        self._stop_auto_refresh()
        if self.key_storage:
            self.key_storage.clear()
            self.key_storage = None
        self.current_user = None

        if self.repo and hasattr(self.repo, 'close'):
            self.repo.close()
        self.repo = None

        if hasattr(self, 'mailbox_view') and self.mailbox_view:
            self.mailbox_view.destroy()

        self.show_login_screen()

    def _schedule_auto_refresh(self):
        """Планирование автообновления"""
        if not self.current_user:
            return
        if hasattr(self, 'mailbox_view') and self.mailbox_view:
            settings = self.mailbox_view.get_auto_refresh_settings()
            if settings["enabled"]:
                interval_ms = settings["interval"] * 1000
                self.auto_refresh_job_id = self.after(interval_ms, self._auto_refresh_callback)

    def _auto_refresh_callback(self):
        """Callback автообновления"""
        if self.current_user and hasattr(self, 'mailbox_view'):
            self.refresh_messages()
            self._schedule_auto_refresh()

    def _stop_auto_refresh(self):
        """Остановка автообновления"""
        if self.auto_refresh_job_id:
            self.after_cancel(self.auto_refresh_job_id)
            self.auto_refresh_job_id = None

    def _save_single_attachment(self, message: Message, attachment: dict, target_path: str):
        """Сохраняет одно вложение письма (сетевой или локальный режим)"""
        if not self.repo:
            return

        success = False
        if hasattr(self.repo, 'download_attachment') and 'id' in attachment:
            success = self.repo.download_attachment(attachment['id'], target_path)
        elif hasattr(self.repo, 'save_attachment'):
            success = self.repo.save_attachment(message.filename, attachment['name'], target_path)

        if success:
            Dialogs.show_info(self, "Успех", f"Вложение сохранено: {attachment['name']}")
        else:
            Dialogs.show_error(self, "Ошибка", "Не удалось сохранить вложение")