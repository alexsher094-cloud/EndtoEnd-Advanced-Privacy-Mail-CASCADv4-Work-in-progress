# app.py
"""
Flask-обёртка над EAPM КАСКАД.
Вся логика — в существующих модулях. Flask только отдаёт JSON.
Поддерживает вложения (локальный и сетевой режимы).
"""
import os
import base64
import tempfile
import secrets
import datetime
from flask import Flask, jsonify, request, send_from_directory, send_file, session

from storage.local_file_repo import LocalFileRepository
from storage.network_repo import NetworkRepository
from encryption.key_storage import KeyStorage
from utils.validators import Validators
from hybrid_steganography import recover_from_key


# ============================================================
# APP
# ============================================================
app = Flask(__name__, static_folder="web", static_url_path="")
app.secret_key = secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024   # 60 МБ на весь запрос


# ============================================================
# СОСТОЯНИЕ (одно на процесс)
# ============================================================
app_state = {
    "repo": None,
    "user": None,
    "key_storage": KeyStorage(),
}


def require_auth():
    if not app_state["repo"] or not app_state["user"]:
        return jsonify({"success": False, "error": "Не авторизован"}), 401
    return None


# ============================================================
# СТАТИКА
# ============================================================
@app.route("/")
def index():
    return send_from_directory("web", "index.html")


# ============================================================
# АВТОРИЗАЦИЯ
# ============================================================
@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json or {}
    login = (data.get("login") or "").strip()
    password = data.get("password") or ""
    mode = data.get("mode", "local")

    if not login or not password:
        return jsonify({"success": False, "error": "Введите логин и пароль"}), 400

    try:
        if mode == "local":
            path = data.get("path") or "./server_data"
            repo = LocalFileRepository(path)
        elif mode == "network":
            server = data.get("server")
            port = int(data.get("port", 443))
            tls = bool(data.get("tls", True))
            if not server:
                return jsonify({"success": False, "error": "Укажите сервер"}), 400
            repo = NetworkRepository(server, port, tls)
        else:
            return jsonify({"success": False, "error": "Неизвестный режим"}), 400

        success, msg = repo.authenticate(login, password)
        if not success:
            return jsonify({"success": False, "error": msg}), 401

        app_state["repo"] = repo
        app_state["user"] = login
        session["user"] = login
        return jsonify({"success": True, "user": login})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.json or {}
    login = (data.get("login") or "").strip()
    password = data.get("password") or ""
    mode = data.get("mode", "local")

    if not login or not password:
        return jsonify({"success": False, "error": "Введите логин и пароль"}), 400

    try:
        if mode == "local":
            path = data.get("path") or "./server_data"
            repo = LocalFileRepository(path)
        elif mode == "network":
            server = data.get("server")
            port = int(data.get("port", 443))
            tls = bool(data.get("tls", True))
            if not server:
                return jsonify({"success": False, "error": "Укажите сервер"}), 400
            repo = NetworkRepository(server, port, tls)
        else:
            return jsonify({"success": False, "error": "Неизвестный режим"}), 400

        success, msg = repo.register_user(login, password)
        return jsonify({
            "success": success,
            "message": msg if success else None,
            "error": None if success else msg,
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/logout", methods=["POST"])
def api_logout():
    repo = app_state.get("repo")
    if repo and hasattr(repo, "close"):
        try:
            repo.close()
        except Exception:
            pass
    app_state["repo"] = None
    app_state["user"] = None
    app_state["key_storage"].clear()
    session.clear()
    return jsonify({"success": True})


# ============================================================
# ПИСЬМА
# ============================================================
def message_to_dict(msg, include_body=False):
    d = {
        "id": msg.filename,
        "folder": msg.folder,
        "sender": msg.sender,
        "recipient": msg.recipient,
        "subject": msg.subject,
        "preview": msg.preview,
        "date": msg.date or "",
        "unread": not msg.is_read,
        "encrypted": msg.is_encrypted,
        "encryptionType": msg.encryption_type,
        "hasStego": msg.has_stego,
        "hasAttachments": msg.has_attachments(),
        "attachments": msg.attachments or [],
    }
    if include_body:
        d["body"] = msg.body_raw
        d["stegoKeyHex"] = msg.get_stego_key_hex() if msg.has_stego else None
    return d


@app.route("/api/messages", methods=["GET"])
def api_messages():
    err = require_auth()
    if err: return err

    folder = request.args.get("folder")
    try:
        messages = app_state["repo"].get_messages_list(app_state["user"])
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    result = []
    for m in messages:
        if folder == "inbox" and m.folder != "inbox": continue
        if folder == "sent"  and m.folder != "sent":  continue
        result.append(message_to_dict(m, include_body=False))

    return jsonify({"success": True, "messages": result})


@app.route("/api/messages/<msg_id>", methods=["GET"])
def api_message_detail(msg_id):
    err = require_auth()
    if err: return err

    try:
        messages = app_state["repo"].get_messages_list(app_state["user"])
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    msg = next((m for m in messages if m.filename == msg_id), None)
    if not msg:
        return jsonify({"success": False, "error": "Письмо не найдено"}), 404

    if hasattr(app_state["repo"], "get_full_message"):
        full = app_state["repo"].get_full_message(msg)
        if full:
            msg.body_raw = full.body_raw
            msg.attachments = full.attachments
            msg.is_read = full.is_read

    if msg.folder == "inbox" and not msg.is_read:
        try:
            if hasattr(app_state["repo"], "mark_message_as_read"):
                app_state["repo"].mark_message_as_read(msg)
            elif hasattr(app_state["repo"], "mark_as_read"):
                app_state["repo"].mark_as_read(app_state["user"], msg.filename)
            msg.is_read = True
        except Exception:
            pass

    return jsonify({"success": True, "message": message_to_dict(msg, include_body=True)})


@app.route("/api/messages/send", methods=["POST"])
def api_send():
    err = require_auth()
    if err: return err

    data = request.json or {}
    to = (data.get("to") or "").strip()
    subject = data.get("subject") or "(без темы)"
    body = data.get("body") or ""
    enc_mode = data.get("encryptionMode")
    enc_key = data.get("encryptionKey")

    if not to or not body:
        return jsonify({"success": False, "error": "Заполните «Кому» и «Сообщение»"}), 400

    # --- Вложения: декодируем base64 → bytes ---
    attachments_raw = data.get("attachments") or []
    attachments = []
    total_size = 0

    for att in attachments_raw:
        name = att.get("name") or "file"
        b64 = att.get("data") or ""
        try:
            raw = base64.b64decode(b64)
        except Exception:
            return jsonify({"success": False, "error": f"Плохие данные файла {name}"}), 400

        total_size += len(raw)
        if total_size > 50 * 1024 * 1024:
            return jsonify({"success": False, "error": "Суммарный размер вложений > 50 МБ"}), 400

        attachments.append((name, raw))

    # Time-based не поддерживает вложения
    if enc_mode == "time" and attachments:
        return jsonify({
            "success": False,
            "error": "Time-based шифрование не поддерживает вложения",
        }), 400

    aes_key = None
    time_salt = None
    time_bucket = None

    try:
        if enc_mode == "aes" and enc_key:
            ok, key_bytes, err_msg = Validators.validate_aes_key(enc_key)
            if not ok:
                return jsonify({"success": False, "error": err_msg}), 400
            aes_key = key_bytes

        elif enc_mode == "time" and enc_key:
            ok, err_msg = Validators.validate_time_salt(enc_key)
            if not ok:
                return jsonify({"success": False, "error": err_msg}), 400
            time_salt = enc_key
            time_bucket = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        success, msg = app_state["repo"].send_message(
            sender=app_state["user"],
            recipient=to,
            subject=subject,
            body=body,
            encryption_mode=enc_mode,
            aes_key=aes_key,
            time_salt=time_salt,
            time_bucket=time_bucket,
            attachments=attachments if attachments else None,
        )
        return jsonify({
            "success": success,
            "message": msg if success else None,
            "error": None if success else msg,
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/messages/<msg_id>", methods=["DELETE"])
def api_delete_message(msg_id):
    err = require_auth()
    if err: return err
    try:
        if hasattr(app_state["repo"], "delete_message"):
            ok = app_state["repo"].delete_message(app_state["user"], msg_id)
        elif hasattr(app_state["repo"], "delete_message_by_server_id"):
            ok = app_state["repo"].delete_message_by_server_id(int(msg_id))
        else:
            return jsonify({"success": False, "error": "Не поддерживается"}), 400
        return jsonify({"success": bool(ok)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/messages/delete-all", methods=["POST"])
def api_delete_all():
    err = require_auth()
    if err: return err
    try:
        result = app_state["repo"].delete_all_messages(app_state["user"])
        count = result if isinstance(result, int) else 0
        return jsonify({"success": True, "deleted": count})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================
# СКАЧИВАНИЕ ВЛОЖЕНИЙ
# ============================================================
@app.route("/api/messages/<msg_id>/attachments/<int:idx>", methods=["GET"])
def api_download_attachment(msg_id, idx):
    err = require_auth()
    if err: return err

    try:
        messages = app_state["repo"].get_messages_list(app_state["user"])
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    msg = next((m for m in messages if m.filename == msg_id), None)
    if not msg:
        return jsonify({"success": False, "error": "Письмо не найдено"}), 404

    # Сетевой режим — подтягиваем метаданные вложений
    if hasattr(app_state["repo"], "get_full_message"):
        full = app_state["repo"].get_full_message(msg)
        if full:
            msg.attachments = full.attachments

    if idx < 0 or idx >= len(msg.attachments or []):
        return jsonify({"success": False, "error": "Вложение не найдено"}), 404

    att = msg.attachments[idx]
    filename = att.get("name") or att.get("filename") or "file"

    try:
        # Локальный режим — читаем с диска
        att_dir = getattr(app_state["repo"], "attachments_dir", None)
        if att_dir:
            stored = att.get("stored") or ""
            path = os.path.join(att_dir, msg_id, stored)
            if not os.path.exists(path):
                return jsonify({"success": False, "error": "Файл не найден на диске"}), 404
            return send_file(path, as_attachment=True, download_name=filename)

        # Сетевой режим — через download_attachment
        if hasattr(app_state["repo"], "download_attachment") and "id" in att:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1])
            tmp.close()
            ok = app_state["repo"].download_attachment(att["id"], tmp.name)
            if not ok:
                return jsonify({"success": False, "error": "Не удалось скачать"}), 500
            return send_file(tmp.name, as_attachment=True, download_name=filename)

        return jsonify({"success": False, "error": "Скачивание не поддерживается"}), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================
# ДЕШИФРОВКА
# ============================================================
@app.route("/api/messages/<msg_id>/decrypt", methods=["POST"])
def api_decrypt(msg_id):
    err = require_auth()
    if err: return err

    data = request.json or {}
    key = (data.get("key") or "").strip()
    if not key:
        return jsonify({"success": False, "error": "Введите ключ"}), 400

    try:
        messages = app_state["repo"].get_messages_list(app_state["user"])
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    msg = next((m for m in messages if m.filename == msg_id), None)
    if not msg:
        return jsonify({"success": False, "error": "Письмо не найдено"}), 404

    if hasattr(app_state["repo"], "get_full_message"):
        full = app_state["repo"].get_full_message(msg)
        if full:
            msg.body_raw = full.body_raw

    try:
        if msg.encryption_type == "aes":
            ok, key_bytes, err_msg = Validators.validate_aes_key(key)
            if not ok:
                return jsonify({"success": False, "error": err_msg}), 400
            plain = app_state["repo"].decrypt_message_body(msg, aes_key=key_bytes)

        elif msg.encryption_type == "time":
            now = datetime.datetime.now()
            buckets = [
                now.strftime("%Y-%m-%d %H:%M"),
                (now - datetime.timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M"),
                (now + datetime.timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M"),
            ]
            plain = None
            last_err = None
            for b in buckets:
                try:
                    plain = app_state["repo"].decrypt_message_body(
                        msg, time_salt=key, time_bucket=b
                    )
                    break
                except Exception as e:
                    last_err = e
            if plain is None:
                raise ValueError(str(last_err) or "Не удалось расшифровать")
        else:
            plain = msg.body_raw

        return jsonify({"success": True, "plaintext": plain})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/messages/<msg_id>/stego", methods=["POST"])
def api_extract_stego(msg_id):
    err = require_auth()
    if err: return err

    data = request.json or {}
    key_hex = (data.get("key") or "").strip().replace(" ", "")
    if len(key_hex) != 64:
        return jsonify({"success": False, "error": "Ключ должен быть 64 hex символа"}), 400

    try:
        messages = app_state["repo"].get_messages_list(app_state["user"])
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    msg = next((m for m in messages if m.filename == msg_id), None)
    if not msg or not msg.has_stego:
        return jsonify({"success": False, "error": "В письме нет скрытых данных"}), 404

    if hasattr(app_state["repo"], "get_full_message"):
        full = app_state["repo"].get_full_message(msg)
        if full:
            msg.body_raw = full.body_raw

    try:
        keyfile_hex = msg.get_stego_key_hex()
        keyfile_bytes = bytes.fromhex(keyfile_hex)
        aes_key = bytes.fromhex(key_hex)
        carrier = msg.clean_body
        secret = recover_from_key(keyfile_bytes, carrier, aes_key)
        return jsonify({"success": True, "secret": secret})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# ============================================================
# МЕНЕДЖЕР КЛЮЧЕЙ
# ============================================================
@app.route("/api/keys", methods=["GET"])
def api_keys():
    ks = app_state["key_storage"]
    return jsonify({
        "success": True,
        "aes":  [{"name": n, "value": base64.b64encode(k).decode()}
                 for n, k in ks.get_all_aes_keys().items()],
        "time": [{"name": n, "value": s}
                 for n, s in ks.get_all_time_salts().items()],
        "num":  [{"value": v} for v in ks.get_all_num_keys()],
    })


@app.route("/api/keys/aes", methods=["POST"])
def api_add_aes():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    key_str = (data.get("key") or "").strip()
    if not name or not key_str:
        return jsonify({"success": False, "error": "Введите имя и ключ"}), 400

    ok, key_bytes, err_msg = Validators.validate_aes_key(key_str)
    if not ok:
        return jsonify({"success": False, "error": err_msg}), 400

    app_state["key_storage"].add_aes_key(name, key_bytes)
    return jsonify({"success": True})


@app.route("/api/keys/aes/<path:name>", methods=["DELETE"])
def api_del_aes(name):
    ok = app_state["key_storage"].delete_aes_key(name)
    return jsonify({"success": ok})


@app.route("/api/keys/time", methods=["POST"])
def api_add_time():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    salt = (data.get("salt") or "").strip()
    if not name or not salt:
        return jsonify({"success": False, "error": "Введите имя и соль"}), 400

    ok, err_msg = Validators.validate_time_salt(salt)
    if not ok:
        return jsonify({"success": False, "error": err_msg}), 400

    app_state["key_storage"].add_time_salt(name, salt)
    return jsonify({"success": True})


@app.route("/api/keys/time/<path:name>", methods=["DELETE"])
def api_del_time(name):
    ok = app_state["key_storage"].delete_time_salt(name)
    return jsonify({"success": ok})


@app.route("/api/keys/num", methods=["POST"])
def api_add_num():
    data = request.json or {}
    key = (data.get("key") or "").strip()
    if not key:
        return jsonify({"success": False, "error": "Введите ключ"}), 400
    app_state["key_storage"].add_num_key(key)
    return jsonify({"success": True})


@app.route("/api/keys/num/<int:idx>", methods=["DELETE"])
def api_del_num(idx):
    ok = app_state["key_storage"].delete_num_key(idx)
    return jsonify({"success": ok})


# ============================================================
# ЗАПУСК
# ============================================================
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)