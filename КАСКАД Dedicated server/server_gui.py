# server_gui.py
import customtkinter as ctk
import socket
import threading
import logging
import sys
import time
import urllib.request
from tkinter import filedialog, messagebox
from config import ServerConfig
from server_core import MailServer
from cert_utils import generate_self_signed_cert

logger = logging.getLogger(__name__)


class ServerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{ServerConfig.APP_NAME} v{ServerConfig.VERSION}")
        self.geometry("750x680")
        self.minsize(700, 600)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.server = None
        self.server_thread = None
        self.stats_update_id = None

        self._create_widgets()
        self._update_local_ip()
        self._setup_logging()

    def _create_widgets(self):
        # ... (без изменений, тот же код, что у вас) ...
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        settings_frame = ctk.CTkFrame(main_frame, corner_radius=12)
        settings_frame.pack(fill="x", pady=(0, 15))

        ip_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        ip_frame.pack(fill="x", padx=15, pady=(15, 5))
        ctk.CTkLabel(ip_frame, text="IP-адрес сервера:", font=("Segoe UI", 12)).pack(side="left")
        self.ip_label = ctk.CTkLabel(ip_frame, text="", font=("Segoe UI", 12, "bold"))
        self.ip_label.pack(side="left", padx=10)

        port_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        port_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(port_frame, text="Порт:", font=("Segoe UI", 12)).pack(side="left")
        self.port_entry = ctk.CTkEntry(port_frame, width=120, placeholder_text=str(ServerConfig.DEFAULT_PORT))
        self.port_entry.insert(0, str(ServerConfig.DEFAULT_PORT))
        self.port_entry.pack(side="left", padx=10)

        self.tls_var = ctk.BooleanVar(value=False)
        self.tls_check = ctk.CTkCheckBox(settings_frame, text="Использовать TLS (SSL)",
                                         variable=self.tls_var, font=("Segoe UI", 12))
        self.tls_check.pack(anchor="w", padx=15, pady=(10, 5))

        self.cert_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        self.cert_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(self.cert_frame, text="Сертификат (.crt):", font=("Segoe UI", 12)).pack(side="left")
        self.cert_entry = ctk.CTkEntry(self.cert_frame, width=250, placeholder_text="server.crt")
        self.cert_entry.insert(0, "server.crt")
        self.cert_entry.pack(side="left", padx=5)
        self.cert_browse_btn = ctk.CTkButton(self.cert_frame, text="Обзор", width=60,
                                             command=self._browse_cert)
        self.cert_browse_btn.pack(side="left")

        self.key_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        self.key_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(self.key_frame, text="Приватный ключ (.key):", font=("Segoe UI", 12)).pack(side="left")
        self.key_entry = ctk.CTkEntry(self.key_frame, width=250, placeholder_text="server.key")
        self.key_entry.insert(0, "server.key")
        self.key_entry.pack(side="left", padx=5)
        self.key_browse_btn = ctk.CTkButton(self.key_frame, text="Обзор", width=60,
                                            command=self._browse_key)
        self.key_browse_btn.pack(side="left")

        btn_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(15, 10))
        self.start_btn = ctk.CTkButton(btn_frame, text="▶ Запустить сервер",
                                       command=self._start_server,
                                       fg_color="#2e6b2e", hover_color="#1e4a1e",
                                       width=150, height=35)
        self.start_btn.pack(side="left", padx=5)
        self.stop_btn = ctk.CTkButton(btn_frame, text="⏹ Остановить сервер",
                                      command=self._stop_server,
                                      fg_color="#8b0000", hover_color="#b22222",
                                      state="disabled", width=150, height=35)
        self.stop_btn.pack(side="left", padx=5)

        status_frame = ctk.CTkFrame(main_frame, corner_radius=12)
        status_frame.pack(fill="x", pady=(0, 15))

        self.status_label = ctk.CTkLabel(status_frame, text="Статус: ○ Остановлен",
                                         font=("Segoe UI", 13, "bold"), text_color="gray")
        self.status_label.pack(anchor="w", padx=15, pady=(10, 5))

        self.connected_label = ctk.CTkLabel(status_frame, text="Подключено пользователей: 0",
                                            font=("Segoe UI", 12))
        self.connected_label.pack(anchor="w", padx=15, pady=(0, 5))

        ip_info_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        ip_info_frame.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(ip_info_frame, text="Локальный IP:", font=("Segoe UI", 12)).pack(side="left")
        self.local_ip_label = ctk.CTkLabel(ip_info_frame, text="", font=("Segoe UI", 12, "bold"))
        self.local_ip_label.pack(side="left", padx=5)

        ctk.CTkLabel(ip_info_frame, text="| Публичный IP:", font=("Segoe UI", 12)).pack(side="left", padx=(15, 0))
        self.public_ip_label = ctk.CTkLabel(ip_info_frame, text="Не определён", font=("Segoe UI", 12, "bold"))
        self.public_ip_label.pack(side="left", padx=5)

        self.refresh_public_ip_btn = ctk.CTkButton(
            ip_info_frame, text="🔄", width=35, height=28,
            command=self._refresh_public_ip,
            fg_color=("#3a6ea5", "#1f538d")
        )
        self.refresh_public_ip_btn.pack(side="left", padx=5)

        self.copy_public_ip_btn = ctk.CTkButton(
            ip_info_frame, text="📋", width=35, height=28,
            command=self._copy_public_ip,
            fg_color=("#3a6ea5", "#1f538d")
        )
        self.copy_public_ip_btn.pack(side="left")

        log_frame = ctk.CTkFrame(main_frame, corner_radius=12)
        log_frame.pack(fill="both", expand=True)
        ctk.CTkLabel(log_frame, text="Лог сервера:", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=15, pady=(10, 5))
        self.log_text = ctk.CTkTextbox(log_frame, wrap="word", font=("Consolas", 11))
        self.log_text.pack(fill="both", expand=True, padx=15, pady=(0, 15))

    def _browse_cert(self):
        f = filedialog.askopenfilename(title="Выберите сертификат (.crt)",
                                       filetypes=[("CRT files", "*.crt"), ("All files", "*.*")])
        if f:
            self.cert_entry.delete(0, "end")
            self.cert_entry.insert(0, f)

    def _browse_key(self):
        f = filedialog.askopenfilename(title="Выберите приватный ключ (.key)",
                                       filetypes=[("KEY files", "*.key"), ("All files", "*.*")])
        if f:
            self.key_entry.delete(0, "end")
            self.key_entry.insert(0, f)

    def _update_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            ip = "127.0.0.1"
        self.ip_label.configure(text=ip)
        self.local_ip_label.configure(text=ip)

    def _setup_logging(self):
        class TextHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget
                self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            def emit(self, record):
                msg = self.format(record)
                def append():
                    self.text_widget.insert("end", msg + "\n")
                    self.text_widget.see("end")
                self.text_widget.after(0, append)

        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        gui_handler = TextHandler(self.log_text)
        gui_handler.setLevel(logging.INFO)
        logging.root.addHandler(gui_handler)

        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        logging.root.addHandler(console)

        logging.root.setLevel(getattr(logging, ServerConfig.LOG_LEVEL))

    def _refresh_public_ip(self):
        self.public_ip_label.configure(text="Определяется...")
        threading.Thread(target=self._fetch_public_ip, daemon=True).start()

    def _fetch_public_ip(self):
        try:
            req = urllib.request.Request(
                "https://api.ipify.org",
                headers={"User-Agent": "EAPM-Server/1.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                ip = response.read().decode('utf-8').strip()
            self.after(0, lambda: self.public_ip_label.configure(text=ip))
        except Exception as e:
            logging.warning(f"Ошибка получения публичного IP: {e}")
            self.after(0, lambda: self.public_ip_label.configure(text="Не удалось определить"))

    def _copy_public_ip(self):
        ip_text = self.public_ip_label.cget("text")
        if ip_text and ip_text not in ("Не определён", "Определяется..."):
            self.clipboard_clear()
            self.clipboard_append(ip_text)
            original = self.copy_public_ip_btn.cget("text")
            self.copy_public_ip_btn.configure(text="✓")
            self.after(1500, lambda: self.copy_public_ip_btn.configure(text=original))

    def _start_server(self):
        port = int(self.port_entry.get() or ServerConfig.DEFAULT_PORT)
        host = "0.0.0.0"

        if self.tls_var.get():
            try:
                cert_path, key_path = generate_self_signed_cert(
                    cert_path=self.cert_entry.get(),
                    key_path=self.key_entry.get(),
                    common_name=socket.gethostname(),
                    force_regen=False
                )
                logging.info(f"Сертификат готов: {cert_path}, ключ: {key_path}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось создать сертификат: {e}")
                return
        else:
            cert_path = key_path = None

        try:
            self.server = MailServer(
                host=host, port=port, max_workers=ServerConfig.MAX_WORKERS,
                use_tls=self.tls_var.get(),
                certfile=cert_path,
                keyfile=key_path
            )
            if not self.tls_var.get():
                if not messagebox.askyesno("Предупреждение", "Вы отключили TLS. Все данные (включая пароли) будут передаваться в открытом виде. Вы можете не использовать TLS в том случае, если используете локальную сеть. Но даже так в этом случае, нельзя гарантировать безопасность ваших данных на уровне канала передачи. Включите TLS. Это не просьба... Продолжить?"):
                    return
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать сервер: {e}")
            return

        self.server_thread = threading.Thread(target=self._run_server_thread, daemon=True)
        self.server_thread.start()

        self.start_btn.configure(state="disabled")
        self.port_entry.configure(state="disabled")
        self.tls_check.configure(state="disabled")
        self.cert_entry.configure(state="disabled")
        self.key_entry.configure(state="disabled")
        self.cert_browse_btn.configure(state="disabled")
        self.key_browse_btn.configure(state="disabled")

        self.after(500, self._check_server_started)

    def _run_server_thread(self):
        try:
            self.server.start()
        except Exception as e:
            self.after(0, lambda: self._on_server_error(str(e)))

    def _check_server_started(self):
        if not self.server:
            return
        if self.server.running:
            self.stop_btn.configure(state="normal")
            self.status_label.configure(text="Статус: ● Запущен", text_color="green")
            self._update_stats()
            logging.info(f"Сервер успешно запущен на порту {self.server.port}")
            self._refresh_public_ip()
        else:
            self._on_server_error("Сервер не запустился. Проверьте порт (возможно, занят) и права на запись.")

    def _on_server_error(self, error_msg):
        messagebox.showerror("Ошибка сервера", error_msg)
        if self.server:
            self.server.stop()
            self.server = None
        self.server_thread = None
        self._enable_controls()
        self.status_label.configure(text="Статус: ○ Остановлен", text_color="gray")
        self.connected_label.configure(text="Подключено пользователей: 0")
        self.public_ip_label.configure(text="Не определён")

    def _enable_controls(self):
        self.start_btn.configure(state="normal")
        self.port_entry.configure(state="normal")
        self.tls_check.configure(state="normal")
        self.cert_entry.configure(state="normal")
        self.key_entry.configure(state="normal")
        self.cert_browse_btn.configure(state="normal")
        self.key_browse_btn.configure(state="normal")
        if self.stats_update_id:
            self.after_cancel(self.stats_update_id)
            self.stats_update_id = None

    def _stop_server(self):
        if not self.server or not self.server.running:
            return
        logging.info("Остановка сервера...")
        self.server.stop()
        # Не ждём завершения потока, чтобы не блокировать GUI
        self.server = None
        self.server_thread = None
        self._enable_controls()
        self.stop_btn.configure(state="disabled")
        self.status_label.configure(text="Статус: ○ Остановлен", text_color="gray")
        self.connected_label.configure(text="Подключено пользователей: 0")
        logging.info("Сервер остановлен")

    def _update_stats(self):
        if self.server and self.server.running:
            stats = self.server.get_stats()
            self.connected_label.configure(text=f"Подключено пользователей: {stats['active_connections']}")
            self.stats_update_id = self.after(2000, self._update_stats)

    def on_closing(self):
        self._stop_server()
        self.destroy()


if __name__ == "__main__":
    app = ServerGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()