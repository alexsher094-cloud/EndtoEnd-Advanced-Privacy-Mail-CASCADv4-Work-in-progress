# gui/decryptor_dialog.py
import customtkinter as ctk
import base64
import datetime
from typing import Optional
from models.message import Message
from server.server_api import ServerAPI
from encryption.aes_cipher import AESCipher
from encryption.time_cipher import TimeCipher
from utils.clipboard import ClipboardManager
from .styles import Styles
from .dialogs import Dialogs

class DecryptorDialog(ctk.CTkToplevel):
    """Интерактивный дешифратор письма с поддержкой шифрования и стеганографии."""

    def __init__(self, parent, message: Message, server_api: ServerAPI):
        super().__init__(parent)
        self.parent = parent
        self.message = message
        self.server = server_api

        self.decrypted_body = None          # расшифрованное основное тело
        self.stego_secret = None             # извлечённое скрытое сообщение
        self.stego_key_bytes = None          # ключ для стеганографии (bytes)

        self.clipboard = ClipboardManager(self)

        self.title("🔓 Дешифратор письма")
        self.geometry("750x650")
        self.minsize(650, 550)
        self.transient(parent)

        #self.grab_set() - никаких грабсетов во благо пользователя!

        self.configure(fg_color=("#f0f0f0", "#1e1e1e"))

        self._create_widgets()
        self._update_ui_state()

    def _create_widgets(self):
        # Основной контейнер с прокруткой (на случай длинного содержимого)
        main_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=15, pady=(15, 10))

        # Информация о письме
        info_frame = ctk.CTkFrame(main_frame, corner_radius=12, fg_color=Styles.CARD_BG,
                                  border_width=1, border_color=Styles.CARD_BORDER)
        info_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(info_frame, text=f"От: {self.message.sender}", font=Styles.FONT_BOLD,
                     anchor="w").pack(anchor="w", padx=15, pady=(10, 2))
        ctk.CTkLabel(info_frame, text=f"Тема: {self.message.subject}", font=Styles.FONT_NORMAL,
                     anchor="w").pack(anchor="w", padx=15, pady=(0, 10))

        # Шаг 1: основное шифрование
        self.step1_frame = ctk.CTkFrame(main_frame, corner_radius=12, fg_color=Styles.CARD_BG,
                                        border_width=1, border_color=Styles.CARD_BORDER)
        self.step1_frame.pack(fill="x", pady=(0, 15))
        self._build_encryption_step()

        # Шаг 2: стеганография
        self.step2_frame = ctk.CTkFrame(main_frame, corner_radius=12, fg_color=Styles.CARD_BG,
                                        border_width=1, border_color=Styles.CARD_BORDER)
        self.step2_frame.pack(fill="x", pady=(0, 15))
        self._build_stego_step()

        # Итоговый результат
        result_frame = ctk.CTkFrame(main_frame, corner_radius=12, fg_color=Styles.CARD_BG,
                                    border_width=1, border_color=Styles.CARD_BORDER)
        result_frame.pack(fill="both", expand=True, pady=(0, 15))
        ctk.CTkLabel(result_frame, text="📄 Итоговый результат:", font=Styles.FONT_BOLD,
                     anchor="w").pack(anchor="w", padx=15, pady=(10, 5))
        self.result_text = ctk.CTkTextbox(result_frame, height=150, wrap="word",
                                          font=Styles.FONT_MONO, corner_radius=8)
        self.result_text.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # Кнопки внизу
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))
        copy_btn = ctk.CTkButton(btn_frame, text="📋 Скопировать результат", width=160,
                                 command=self._copy_result, fg_color=Styles.BTN_COLOR,
                                 hover_color=Styles.BTN_HOVER)
        copy_btn.pack(side="left", padx=(0, 10))
        close_btn = ctk.CTkButton(btn_frame, text="Закрыть", width=100,
                                  command=self.destroy, fg_color=Styles.BTN_COLOR,
                                  hover_color=Styles.BTN_HOVER)
        close_btn.pack(side="right")

    def _build_encryption_step(self):
        """Блок расшифровки основного сообщения."""
        header = ctk.CTkFrame(self.step1_frame, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(10, 5))
        ctk.CTkLabel(header, text="🔐 Шаг 1: Основное шифрование", font=Styles.FONT_BOLD,
                     anchor="w").pack(side="left")

        self.enc_status_label = ctk.CTkLabel(header, text="⚪ Не расшифровано",
                                             font=Styles.FONT_SMALL, text_color="gray")
        self.enc_status_label.pack(side="right")

        content = ctk.CTkFrame(self.step1_frame, fg_color="transparent")
        content.pack(fill="x", padx=15, pady=(0, 15))

        # Тип шифрования
        enc_type = self.message.encryption_type
        type_text = "Нет" if not enc_type else ("AES-256" if enc_type == "aes" else "Time-based")
        ctk.CTkLabel(content, text=f"Тип шифрования: {type_text}",
                     font=Styles.FONT_NORMAL).pack(anchor="w", pady=(0, 10))

        if enc_type:
            # Поле для ввода ключа/соли
            self.key_frame = ctk.CTkFrame(content, fg_color="transparent")
            self.key_frame.pack(fill="x", pady=(0, 10))
            self.key_label = ctk.CTkLabel(self.key_frame, text="Ключ (base64/hex):",
                                          font=Styles.FONT_NORMAL)
            self.key_label.pack(anchor="w")
            self.key_entry = self.clipboard.create_entry_with_clipboard(
                self.key_frame, placeholder_text="Введите ключ или соль",
                font=Styles.FONT_MONO, height=35, corner_radius=8
            )
            self.key_entry.pack(fill="x", pady=(2, 5))

            # Кнопка расшифровки
            self.decrypt_btn = ctk.CTkButton(content, text="🔓 Расшифровать",
                                             command=self._decrypt_main,
                                             fg_color=Styles.BTN_COLOR,
                                             hover_color=Styles.BTN_HOVER,
                                             corner_radius=8)
            self.decrypt_btn.pack(pady=(0, 10))

            # Кнопка показа расшифрованного текста
            self.show_plain_btn = ctk.CTkButton(content, text="📄 Показать расшифрованный текст",
                                                command=self._show_decrypted_body,
                                                fg_color=Styles.BTN_COLOR,
                                                hover_color=Styles.BTN_HOVER,
                                                state="disabled", corner_radius=8)
            self.show_plain_btn.pack(pady=(0, 5))

            # Настройка UI под тип шифрования
            if enc_type == "time":
                self.key_label.configure(text="Соль (6-256 символов):")
        else:
            # Письмо не зашифровано – показываем кнопку "Показать оригинал"
            self.show_plain_btn = ctk.CTkButton(content, text="📄 Показать текст письма",
                                                command=self._show_original_body,
                                                fg_color=Styles.BTN_COLOR,
                                                hover_color=Styles.BTN_HOVER,
                                                corner_radius=8)
            self.show_plain_btn.pack(pady=(0, 5))

    def _build_stego_step(self):
        """Блок извлечения скрытого сообщения (стеганография)."""
        header = ctk.CTkFrame(self.step2_frame, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(10, 5))
        ctk.CTkLabel(header, text="📦 Шаг 2: Скрытое сообщение (стеганография)",
                     font=Styles.FONT_BOLD, anchor="w").pack(side="left")
        self.stego_status_label = ctk.CTkLabel(header, text="⚪ Не обнаружено",
                                               font=Styles.FONT_SMALL, text_color="gray")
        self.stego_status_label.pack(side="right")

        content = ctk.CTkFrame(self.step2_frame, fg_color="transparent")
        content.pack(fill="x", padx=15, pady=(0, 15))

        if self.message.has_stego:
            self.stego_status_label.configure(text="🔍 Маркер найден", text_color="orange")
            # Показать посылку (carrier) – очищенное тело без маркера
            carrier = self.message.clean_body[:200] + ("..." if len(self.message.clean_body) > 200 else "")
            ctk.CTkLabel(content, text=f"Посылка (первые 200 символов):\n{carrier}",
                         font=Styles.FONT_SMALL, wraplength=600, justify="left",
                         anchor="w").pack(anchor="w", pady=(0, 10))

            # Поле для AES-ключа (64 hex)
            key_frame = ctk.CTkFrame(content, fg_color="transparent")
            key_frame.pack(fill="x", pady=(0, 10))
            ctk.CTkLabel(key_frame, text="AES-ключ (64 hex символа):",
                         font=Styles.FONT_NORMAL).pack(anchor="w")
            self.stego_key_entry = self.clipboard.create_entry_with_clipboard(
                key_frame, placeholder_text="Введите ключ для стеганографии",
                font=Styles.FONT_MONO, height=35, corner_radius=8
            )
            self.stego_key_entry.pack(fill="x", pady=(2, 5))

            # Кнопка генерации случайного ключа (только для удобства, при извлечении не нужна)
            # Но можно оставить для тестов
            gen_stego_key_btn = ctk.CTkButton(key_frame, text="Сгенерировать",
                                              width=100, command=self._gen_stego_key,
                                              fg_color=Styles.BTN_COLOR)
            gen_stego_key_btn.pack(pady=(2, 0))

            # Кнопка извлечения
            self.extract_stego_btn = ctk.CTkButton(content, text="📩 Извлечь скрытое сообщение",
                                                   command=self._extract_stego,
                                                   fg_color=Styles.BTN_COLOR,
                                                   hover_color=Styles.BTN_HOVER,
                                                   corner_radius=8)
            self.extract_stego_btn.pack(pady=(0, 10))

            # Кнопка показа извлечённого
            self.show_stego_btn = ctk.CTkButton(content, text="🔎 Показать скрытое сообщение",
                                                command=self._show_stego_secret,
                                                fg_color=Styles.BTN_COLOR,
                                                hover_color=Styles.BTN_HOVER,
                                                state="disabled", corner_radius=8)
            self.show_stego_btn.pack(pady=(0, 5))
        else:
            self.stego_status_label.configure(text="❌ Отсутствует", text_color="gray")
            ctk.CTkLabel(content, text="В этом письме нет стеганографического ключа.",
                         font=Styles.FONT_NORMAL, text_color="gray").pack(anchor="w")

    # ---------- Логика шага 1 ----------
    def _decrypt_main(self):
        enc_type = self.message.encryption_type
        if not enc_type:
            Dialogs.show_info(self, "Информация", "Письмо не зашифровано")
            return

        key_value = self.key_entry.get().strip()
        if not key_value:
            Dialogs.show_error(self, "Ошибка", "Введите ключ или соль")
            return

        try:
            if enc_type == "aes":
                from utils.validators import Validators
                valid, key_bytes, error = Validators.validate_aes_key(key_value)
                if not valid:
                    Dialogs.show_error(self, "Ошибка", error)
                    return
                self.decrypted_body = self.server.decrypt_message_body(
                    self.message, aes_key=key_bytes
                )
            elif enc_type == "time":
                # Для time-based пробуем текущую минуту и соседние
                now = datetime.datetime.now()
                buckets = [
                    now.strftime("%Y-%m-%d %H:%M"),
                    (now - datetime.timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M"),
                    (now + datetime.timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
                ]
                success = False
                for bucket in buckets:
                    try:
                        self.decrypted_body = self.server.decrypt_message_body(
                            self.message, time_salt=key_value, time_bucket=bucket
                        )
                        success = True
                        break
                    except Exception:
                        continue
                if not success:
                    raise ValueError("Не удалось расшифровать ни в одном временном интервале")
            # Обновляем статус и кнопки
            self.enc_status_label.configure(text="✅ Расшифровано", text_color="green")
            self.show_plain_btn.configure(state="normal")
            self.decrypt_btn.configure(state="disabled")
            self._update_result()
        except Exception as e:
            Dialogs.show_error(self, "Ошибка расшифровки", str(e))

    def _show_decrypted_body(self):
        if self.decrypted_body:
            self.result_text.delete("1.0", "end")
            self.result_text.insert("1.0", self.decrypted_body)
        else:
            Dialogs.show_warning(self, "Внимание", "Сначала расшифруйте письмо")

    def _show_original_body(self):
        # Для незашифрованного письма сразу показываем оригинал
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", self.message.body_raw)

    # ---------- Логика шага 2 ----------
    def _gen_stego_key(self):
        import secrets
        key = secrets.token_hex(32)
        self.stego_key_entry.delete(0, "end")
        self.stego_key_entry.insert(0, key)

    def _extract_stego(self):
        if not self.message.has_stego:
            Dialogs.show_warning(self, "Внимание", "В письме нет стего-ключа")
            return
        key_hex = self.stego_key_entry.get().strip().replace(" ", "")
        if len(key_hex) != 64:
            Dialogs.show_error(self, "Ошибка", "Ключ должен быть 64 hex символа (32 байта)")
            return
        try:
            aes_key = bytes.fromhex(key_hex)
        except ValueError:
            Dialogs.show_error(self, "Ошибка", "Неверный hex-ключ")
            return

        try:
            from hybrid_steganography import recover_from_key
            keyfile_hex = self.message.get_stego_key_hex()
            if not keyfile_hex:
                raise ValueError("Не найден ключ-файл в письме")
            keyfile_bytes = bytes.fromhex(keyfile_hex)
            carrier = self.message.clean_body
            self.stego_secret = recover_from_key(keyfile_bytes, carrier, aes_key)
            self.stego_status_label.configure(text="✅ Извлечено", text_color="green")
            self.show_stego_btn.configure(state="normal")
            self.extract_stego_btn.configure(state="disabled")
            self._update_result()
        except Exception as e:
            Dialogs.show_error(self, "Ошибка извлечения", str(e))

    def _show_stego_secret(self):
        if self.stego_secret:
            self.result_text.delete("1.0", "end")
            self.result_text.insert("1.0", self.stego_secret)
        else:
            Dialogs.show_warning(self, "Внимание", "Сначала извлеките скрытое сообщение")

    # ---------- Общие методы ----------
    def _update_result(self):
        """Обновляет итоговый текст, показывая, что доступно."""
        output_parts = []
        if self.decrypted_body:
            output_parts.append("=== Расшифрованное основное сообщение ===\n")
            output_parts.append(self.decrypted_body)
        if self.stego_secret:
            if output_parts:
                output_parts.append("\n\n=== Извлечённое скрытое сообщение ===\n")
            else:
                output_parts.append("=== Скрытое сообщение ===\n")
            output_parts.append(self.stego_secret)
        if not output_parts:
            output_parts.append("Ничего не расшифровано и не извлечено.\nИспользуйте кнопки выше.")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", "".join(output_parts))

    def _copy_result(self):
        text = self.result_text.get("1.0", "end-1c").strip()
        if text:
            self.clipboard.copy_to_clipboard(text)
            Dialogs.show_info(self, "Скопировано", "Результат скопирован в буфер обмена")
        else:
            Dialogs.show_warning(self, "Нет данных", "Нечего копировать")

    def _update_ui_state(self):
        """Дополнительная инициализация (меняет подсказки для time)."""
        if self.message.encryption_type == "time":
            self.key_label.configure(text="Соль (6-256 символов):")