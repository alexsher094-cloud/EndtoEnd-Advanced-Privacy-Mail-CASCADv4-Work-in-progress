/* ============================================================
   STATE
   ============================================================ */
const state = {
    currentUser: null,
    storageMode: "local",
    filter: "all",                 // ← "all" по умолчанию, а не "inbox"
    selectedMessageId: null,
    selectedMessage: null,
    composeAttachments: [],        // [{ name, size, data(base64), mime }]
    keys: { aes: [], time: [], num: [] },
    messages: [],
};

const ICON = {
    lock: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="4" y="10" width="16" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>`,
    box:  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M3 7l9-4 9 4-9 4-9-4z"/><path d="M3 12l9 4 9-4M3 17l9 4 9-4"/></svg>`,
    clip: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>`
};

/* ============================================================
   API
   ============================================================ */
async function api(path, options = {}) {
    const opts = {
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        ...options,
    };
    if (opts.body && typeof opts.body === "object") {
        opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(path, opts);
    let data;
    try {
        data = await res.json();
    } catch {
        data = { success: false, error: `HTTP ${res.status}` };
    }
    return data;
}

/* ============================================================
   UTILS
   ============================================================ */
const $  = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function show(el) { el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function initials(name) {
    if (!name) return "?";
    return name.split(" ").map(w => w[0]).filter(Boolean).slice(0, 2).join("").toUpperCase();
}

function formatSize(bytes) {
    if (!bytes) return "0 Б";
    if (bytes > 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + " МБ";
    if (bytes > 1024) return Math.round(bytes / 1024) + " КБ";
    return bytes + " Б";
}

function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            // data:xxx;base64,AAAA → берём только AAAA
            const base64 = reader.result.split(",")[1];
            resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

function toast(text, type = "info") {
    const el = document.createElement("div");
    el.className = "toast " + type;
    el.textContent = text;
    $("#toasts").appendChild(el);
    setTimeout(() => {
        el.style.opacity = "0";
        el.style.transform = "translateY(12px)";
        el.style.transition = "all 0.25s";
        setTimeout(() => el.remove(), 260);
    }, 2600);
}

function openModal(id) { show($("#" + id)); }
function closeModal(id) { hide($("#" + id)); }

$$("[data-close]").forEach(el => {
    el.addEventListener("click", () => closeModal(el.dataset.close));
});

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") $$(".modal").forEach(m => hide(m));
});

function playCardEnter(card) {
    card.classList.remove("leaving", "entering");
    void card.offsetWidth;
    card.classList.add("entering");
    setTimeout(() => card.classList.remove("entering"), 500);
}

/* ============================================================
   LOGIN
   ============================================================ */
$$('input[name="storage-mode"]').forEach(radio => {
    radio.addEventListener("change", () => {
        const mode = document.querySelector('input[name="storage-mode"]:checked').value;
        state.storageMode = mode;
        if (mode === "local") {
            show($("#params-local"));
            hide($("#params-network"));
        } else {
            hide($("#params-local"));
            show($("#params-network"));
        }
    });
});

function showLoginStatus(text, type = "") {
    const status = $("#login-status");
    status.textContent = text;
    status.className = "status-line " + type;
    setTimeout(() => {
        status.textContent = "";
        status.className = "status-line";
    }, 3000);
}

function collectLoginParams() {
    if (state.storageMode === "local") {
        return { path: $("#local-path").value.trim() || "./server_data" };
    } else {
        return {
            server: $("#server-addr").value.trim(),
            port: parseInt($("#server-port").value) || 443,
            tls: $("#server-tls").checked,
        };
    }
}

$("#btn-login").addEventListener("click", async () => {
    const login = $("#login-input").value.trim();
    const password = $("#password-input").value;
    if (!login || !password) {
        showLoginStatus("Введите логин и пароль", "error");
        return;
    }
    const params = collectLoginParams();
    const result = await api("/api/login", {
        method: "POST",
        body: { login, password, mode: state.storageMode, ...params },
    });
    if (!result.success) {
        showLoginStatus(result.error || "Ошибка входа", "error");
        return;
    }
    loginSuccess(login);
});

$("#btn-register").addEventListener("click", async () => {
    const login = $("#login-input").value.trim();
    const password = $("#password-input").value;
    if (!login || !password) {
        showLoginStatus("Введите логин и пароль", "error");
        return;
    }
    const params = collectLoginParams();
    const result = await api("/api/register", {
        method: "POST",
        body: { login, password, mode: state.storageMode, ...params },
    });
    if (!result.success) {
        showLoginStatus(result.error || "Ошибка регистрации", "error");
        return;
    }
    toast("Регистрация успешна. Выполняется вход...", "success");
    const loginResult = await api("/api/login", {
        method: "POST",
        body: { login, password, mode: state.storageMode, ...params },
    });
    if (loginResult.success) {
        setTimeout(() => loginSuccess(login), 400);
    } else {
        showLoginStatus("Зарегистрировано, но войти не удалось", "error");
    }
});

$("#btn-browse").addEventListener("click", () => {
    toast("Выбор папки: укажите путь вручную", "info");
});

function loginSuccess(login) {
    state.currentUser = login;

    const loginScreen = $("#screen-login");
    const card = loginScreen.querySelector(".login-card");
    const mailbox = $("#screen-mailbox");

    card.classList.remove("entering");
    void card.offsetWidth;
    card.classList.add("leaving");

    setTimeout(async () => {
        hide(loginScreen);
        card.classList.remove("leaving");

        $("#topbar-user").textContent = login;
        show(mailbox);

        mailbox.classList.remove("leaving");
        void mailbox.offsetWidth;
        mailbox.classList.add("entering");

        await loadMessages();
        await loadKeys();
        staggerMessages(0.1);

        setTimeout(() => mailbox.classList.remove("entering"), 1000);
    }, 320);

    setTimeout(() => toast("Добро пожаловать, " + login, "success"), 900);
}

function staggerMessages(baseDelay = 0.08) {
    document.querySelectorAll(".message-item").forEach((el, i) => {
        el.classList.add("stagger-in");
        el.style.animationDelay = (i * baseDelay) + "s";
    });
}

/* ============================================================
   LOGOUT
   ============================================================ */
$("#btn-logout").addEventListener("click", () => {
    const mailbox = $("#screen-mailbox");
    const loginScreen = $("#screen-login");
    const card = loginScreen.querySelector(".login-card");

    mailbox.classList.remove("entering");
    void mailbox.offsetWidth;
    mailbox.classList.add("leaving");

    setTimeout(async () => {
        hide(mailbox);
        mailbox.classList.remove("leaving");

        try { await api("/api/logout", { method: "POST" }); } catch {}

        state.currentUser = null;
        state.selectedMessageId = null;
        state.selectedMessage = null;
        state.messages = [];

        $("#login-input").value = "";
        $("#password-input").value = "";

        show(loginScreen);
        playCardEnter(card);
        setTimeout(() => $("#login-input").focus(), 400);
    }, 350);

    toast("Вы вышли из системы", "info");
});

/* ============================================================
   СПИСОК ПИСЕМ
   ============================================================ */
async function loadMessages() {
    const folder = state.filter === "all" ? "" : `?folder=${state.filter}`;
    const result = await api("/api/messages" + folder);

    if (!result.success) {
        toast(result.error || "Ошибка загрузки писем", "error");
        return;
    }

    state.messages = result.messages;
    renderMessages();
}

function renderMessages() {
    const list = $("#message-list");
    list.innerHTML = "";

    if (!state.messages.length) {
        show($("#list-empty"));
        return;
    }
    hide($("#list-empty"));

    state.messages.forEach(msg => {
        const el = document.createElement("div");
        el.className = "message-item" + (msg.unread ? " unread" : "");
        if (msg.id === state.selectedMessageId) el.classList.add("active");

        const lockIcon = msg.encrypted
            ? `<span class="item-lock">${ICON.lock}</span>`
            : "";

        el.innerHTML = `
            <div class="msg-list-avatar">${initials(msg.sender)}</div>
            <div class="msg-list-content">
                <div class="msg-list-top">
                    <span class="msg-list-sender">${escapeHtml(msg.sender)}</span>
                    <span class="msg-list-date">${escapeHtml(msg.date || "—")}</span>
                </div>
                <div class="msg-list-subject">
                    ${lockIcon}
                    <span style="overflow:hidden;text-overflow:ellipsis">${escapeHtml(msg.subject)}</span>
                </div>
                <div class="msg-list-preview">${escapeHtml(msg.preview)}</div>
            </div>
        `;

        el.addEventListener("click", () => openMessage(msg.id));
        list.appendChild(el);
    });
}

async function openMessage(id) {
    const result = await api(`/api/messages/${encodeURIComponent(id)}`);
    if (!result.success) {
        toast(result.error || "Ошибка загрузки письма", "error");
        return;
    }

    const msg = result.message;
    state.selectedMessageId = id;
    state.selectedMessage = msg;

    const localMsg = state.messages.find(m => m.id === id);
    if (localMsg) localMsg.unread = false;

    hide($("#content-empty"));
    show($("#message-view"));

    const view = $("#message-view");
    view.classList.remove("msg-switching");
    void view.offsetWidth;
    view.classList.add("msg-switching");

    $("#msg-subject").textContent = msg.subject;
    $("#msg-from").textContent = msg.sender;
    $("#msg-to").textContent = msg.recipient;
    $("#msg-date").textContent = msg.date || "—";
    $("#msg-body").textContent = msg.encrypted
        ? "[Зашифровано]\n\nЭто письмо зашифровано. Нажмите «Дешифровать», чтобы увидеть содержимое."
        : msg.body;

    $("#msg-avatar").textContent = initials(msg.sender);

    // Бейджи
    const badges = $("#msg-badges");
    badges.innerHTML = "";
    if (msg.encrypted) {
        const label = msg.encryptionType === "aes" ? "AES-256" : "Time-based";
        badges.innerHTML += `<span class="badge encrypted">${ICON.lock}${label}</span>`;
    }
    if (msg.hasStego) badges.innerHTML += `<span class="badge stego">${ICON.box}Стего</span>`;
    if (msg.attachments && msg.attachments.length) {
        badges.innerHTML += `<span class="badge attachment">${ICON.clip}${msg.attachments.length}</span>`;
    }

    // Вложения
    const attBox = $("#msg-attachments");
    const attList = $("#attachments-list");
    attList.innerHTML = "";
    if (msg.attachments && msg.attachments.length) {
        show(attBox);
        msg.attachments.forEach((att, idx) => {
            const el = document.createElement("div");
            el.className = "attachment-item";
            el.innerHTML = `
                <div class="att-name">${ICON.clip}<span>${escapeHtml(att.name || "файл")}</span></div>
                <div style="display:flex;gap:10px;align-items:center">
                    <span class="att-size">${formatSize(att.size)}</span>
                    <button class="btn small ghost">Сохранить</button>
                </div>
            `;
            el.querySelector("button").addEventListener("click", (e) => {
                e.stopPropagation();
                downloadAttachment(msg.id, idx, att.name);
            });
            attList.appendChild(el);
        });
    } else {
        hide(attBox);
    }

    // Перегружаем список (обновится unread-индикатор)
    const listResult = await api("/api/messages" + (state.filter === "all" ? "" : `?folder=${state.filter}`));
    if (listResult.success) {
        state.messages = listResult.messages;
        renderMessages();
    }
}

async function downloadAttachment(msgId, idx, filename) {
    const url = `/api/messages/${encodeURIComponent(msgId)}/attachments/${idx}`;

    try {
        // Таймаут 30 сек — если Flask не ответит, отвалимся с ошибкой
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);

        const res = await fetch(url, { signal: controller.signal });
        clearTimeout(timeoutId);

        if (!res.ok) {
            let errText = `HTTP ${res.status}`;
            try {
                const data = await res.json();
                errText = data.error || errText;
            } catch {}
            toast("Не удалось скачать: " + errText, "error");
            return;
        }

        // Получаем файл как blob
        const blob = await res.blob();

        // Создаём временную ссылку и кликаем — это асинхронно и НЕ блокирует UI
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = blobUrl;
        a.download = filename || "file";
        document.body.appendChild(a);
        a.click();
        a.remove();

        // Освобождаем память
        setTimeout(() => URL.revokeObjectURL(blobUrl), 2000);

        toast("Скачано: " + filename, "success");
    } catch (e) {
        if (e.name === "AbortError") {
            toast("Превышено время ожидания (30 сек)", "error");
        } else {
            toast("Ошибка скачивания: " + e.message, "error");
        }
    }
}

$$(".filter-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
        $$(".filter-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.filter = btn.dataset.filter;
        await loadMessages();
    });
});

/* ============================================================
   COMPOSE
   ============================================================ */
$("#btn-compose").addEventListener("click", () => {
    openModal("modal-compose");
    setTimeout(() => $("#compose-to").focus(), 100);
});

$$('input[name="enc-mode"]').forEach(radio => {
    radio.addEventListener("change", () => {
        const mode = document.querySelector('input[name="enc-mode"]:checked').value;
        const block = $("#enc-key-block");
        const label = $("#enc-key-label");

        if (mode === "none") {
            hide(block);
        } else if (mode === "aes") {
            show(block);
            label.textContent = "Ключ (base64/hex)";
        } else if (mode === "time") {
            show(block);
            label.textContent = "Соль (6–256 символов)";
        }
        $("#enc-key").value = "";
    });
});

$("#btn-gen-key").addEventListener("click", () => {
    const bytes = new Uint8Array(32);
    crypto.getRandomValues(bytes);
    $("#enc-key").value = btoa(String.fromCharCode(...bytes));
    toast("Ключ сгенерирован", "success");
});

$("#stego-toggle").addEventListener("change", (e) => {
    if (e.target.checked) show($("#stego-content"));
    else hide($("#stego-content"));
});

$("#btn-gen-stego").addEventListener("click", () => {
    const bytes = new Uint8Array(32);
    crypto.getRandomValues(bytes);
    $("#stego-key").value = Array.from(bytes).map(b => b.toString(16).padStart(2, "0")).join("");
    toast("Ключ стенографии сгенерирован", "success");
});

$("#btn-gen-keyfile").addEventListener("click", () => {
    const secret = $("#stego-msg").value.trim();
    const carrier = $("#compose-body").value.trim();
    const key = $("#stego-key").value.trim();
    if (!secret || !carrier || !key) {
        toast("Заполните все поля стенографии", "error");
        return;
    }
    const bytes = new Uint8Array(48);
    crypto.getRandomValues(bytes);
    $("#stego-keyfile").value = Array.from(bytes).map(b => b.toString(16).padStart(2, "0")).join("");
    toast("Ключ-файл сгенерирован", "success");
});

/* ============================================================
   ВЛОЖЕНИЯ — выбор файлов
   ============================================================ */
$("#btn-add-file").addEventListener("click", () => {
    $("#file-input").click();
});

$("#file-input").addEventListener("change", async (e) => {
    const files = Array.from(e.target.files);

    for (const file of files) {
        if (file.size > 10 * 1024 * 1024) {
            toast(`«${file.name}» больше 10 МБ`, "error");
            continue;
        }
        try {
            const base64 = await fileToBase64(file);
            state.composeAttachments.push({
                name: file.name,
                size: file.size,
                data: base64,
                mime: file.type || "application/octet-stream",
            });
        } catch {
            toast(`Не удалось прочитать «${file.name}»`, "error");
        }
    }

    e.target.value = "";   // сбрасываем, чтобы можно было выбрать тот же файл снова
    renderComposeAttachments();
});

$("#btn-clear-files").addEventListener("click", () => {
    state.composeAttachments = [];
    renderComposeAttachments();
});

function renderComposeAttachments() {
    const box = $("#compose-attachments");
    if (!state.composeAttachments.length) {
        box.innerHTML = '<div class="muted small center">Нет вложений</div>';
        return;
    }
    box.innerHTML = "";
    state.composeAttachments.forEach((att, i) => {
        const row = document.createElement("div");
        row.className = "att-entry";
        row.innerHTML = `
            <div class="name">
                ${ICON.clip}
                <span>${escapeHtml(att.name)}</span>
                <span class="muted small">${formatSize(att.size)}</span>
            </div>
            <span class="remove">✕</span>
        `;
        row.querySelector(".remove").addEventListener("click", () => {
            state.composeAttachments.splice(i, 1);
            renderComposeAttachments();
        });
        box.appendChild(row);
    });
}

/* ============================================================
   ОТПРАВКА
   ============================================================ */
$("#btn-send").addEventListener("click", async () => {
    const to = $("#compose-to").value.trim();
    const subject = $("#compose-subject").value.trim() || "(без темы)";
    const body = $("#compose-body").value.trim();
    if (!to || !body) {
        toast("Заполните поля «Кому» и «Сообщение»", "error");
        return;
    }

    const encMode = document.querySelector('input[name="enc-mode"]:checked').value;
    const encKey = $("#enc-key").value.trim();

    if (encMode !== "none" && !encKey) {
        toast("Введите ключ или соль", "error");
        return;
    }

    // Проверка: time-based + вложения = не поддерживается
    if (encMode === "time" && state.composeAttachments.length > 0) {
        toast("Time-based шифрование не поддерживает вложения", "error");
        return;
    }

    // Блокируем кнопку от двойного клика
    const sendBtn = $("#btn-send");
    sendBtn.disabled = true;
    const oldText = sendBtn.innerHTML;
    sendBtn.innerHTML = "Отправка...";

    try {
        const result = await api("/api/messages/send", {
            method: "POST",
            body: {
                to, subject, body,
                encryptionMode: encMode === "none" ? null : encMode,
                encryptionKey: encKey || null,
                attachments: state.composeAttachments.map(a => ({
                    name: a.name,
                    data: a.data,
                    mime: a.mime,
                })),
            },
        });

        if (!result.success) {
            toast(result.error || "Ошибка отправки", "error");
            return;
        }

        closeModal("modal-compose");
        resetCompose();
        toast("Письмо отправлено", "success");
        await loadMessages();
    } finally {
        sendBtn.disabled = false;
        sendBtn.innerHTML = oldText;
    }
});

function resetCompose() {
    $("#compose-to").value = "";
    $("#compose-subject").value = "";
    $("#compose-body").value = "";
    $("#enc-key").value = "";
    $("#stego-msg").value = "";
    $("#stego-key").value = "";
    $("#stego-keyfile").value = "";
    $("#stego-toggle").checked = false;
    hide($("#stego-content"));
    hide($("#enc-key-block"));
    $$('input[name="enc-mode"]')[0].checked = true;
    state.composeAttachments = [];
    renderComposeAttachments();
}

/* ============================================================
   ДЕШИФРАТОР
   ============================================================ */
$("#btn-decrypt").addEventListener("click", () => {
    const msg = state.selectedMessage;
    if (!msg) { toast("Сначала выберите письмо", "error"); return; }

    $("#dec-sender").textContent = msg.sender;
    $("#dec-subject").textContent = msg.subject;

    const typeMap = { aes: "AES-256", time: "Time-based" };
    $("#dec-type").textContent = msg.encryptionType ? typeMap[msg.encryptionType] : "Нет";

    $("#dec-step1-status").textContent = "не расшифровано";
    $("#dec-step1-status").className = "status-pill";
    $("#btn-decrypt-main").disabled = false;
    $("#dec-key").value = "";
    $("#dec-key-label").textContent = msg.encryptionType === "time"
        ? "Соль (6–256 символов)"
        : "Ключ (base64/hex)";

    if (msg.hasStego) {
        $("#dec-step2-status").textContent = "маркер найден";
        $("#dec-step2-status").className = "status-pill warning";
        $("#dec-carrier").textContent = "Посылка: " + (msg.body || "").slice(0, 80) + "...";
    } else {
        $("#dec-step2-status").textContent = "отсутствует";
        $("#dec-step2-status").className = "status-pill";
        $("#dec-carrier").textContent = "В этом письме нет скрытых данных.";
    }
    $("#btn-extract-stego-main").disabled = !msg.hasStego;
    $("#dec-stego-key").value = "";

    $("#dec-result").value = "";
    openModal("modal-decryptor");
});

$("#btn-decrypt-main").addEventListener("click", async () => {
    const key = $("#dec-key").value.trim();
    if (!key) { toast("Введите ключ или соль", "error"); return; }

    const msgId = state.selectedMessage.id;
    const result = await api(`/api/messages/${encodeURIComponent(msgId)}/decrypt`, {
        method: "POST",
        body: { key },
    });

    if (!result.success) {
        toast(result.error || "Не удалось расшифровать", "error");
        return;
    }

    $("#dec-step1-status").textContent = "расшифровано";
    $("#dec-step1-status").className = "status-pill success";
    $("#btn-decrypt-main").disabled = true;
    $("#dec-result").value = result.plaintext;
    toast("Письмо расшифровано", "success");
});

$("#btn-extract-stego-main").addEventListener("click", async () => {
    const key = $("#dec-stego-key").value.trim();
    if (key.length !== 64) { toast("Ключ должен быть 64 hex символа", "error"); return; }

    const msgId = state.selectedMessage.id;
    const result = await api(`/api/messages/${encodeURIComponent(msgId)}/stego`, {
        method: "POST",
        body: { key },
    });

    if (!result.success) {
        toast(result.error || "Не удалось извлечь", "error");
        return;
    }

    $("#dec-step2-status").textContent = "извлечено";
    $("#dec-step2-status").className = "status-pill success";
    $("#btn-extract-stego-main").disabled = true;
    $("#dec-result").value = result.secret;
    toast("Скрытое сообщение извлечено", "success");
});

$("#btn-copy-result").addEventListener("click", () => {
    const text = $("#dec-result").value;
    if (!text) { toast("Нечего копировать", "error"); return; }
    navigator.clipboard.writeText(text).then(() => toast("Скопировано", "success"));
});

/* ============================================================
   МЕНЕДЖЕР КЛЮЧЕЙ
   ============================================================ */
$("#btn-keys").addEventListener("click", async () => {
    openModal("modal-keys");
    await loadKeys();
});

$$("#keys-tabs .tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        $$("#keys-tabs .tab-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        $$(".tab-pane").forEach(p => hide(p));
        show($("#tab-" + btn.dataset.tab));
    });
});

async function loadKeys() {
    const result = await api("/api/keys");
    if (!result.success) return;
    state.keys = {
        aes: result.aes || [],
        time: result.time || [],
        num: result.num || [],
    };
    renderKeys();
}

function renderKeys() {
    renderKeyList("#aes-list", "aes");
    renderKeyList("#time-list", "time");
    renderKeyList("#num-list", "num");
}

function renderKeyList(selector, type) {
    const container = $(selector);
    container.innerHTML = "";
    const list = state.keys[type] || [];

    if (!list.length) {
        container.innerHTML = '<p class="muted small" style="padding:10px">Нет сохранённых ключей</p>';
        return;
    }

    list.forEach((item, idx) => {
        const el = document.createElement("div");
        el.className = "key-item";
        const name = item.name || `#${idx + 1}`;
        const value = item.value;

        el.innerHTML = `
            <div class="key-info">
                <div class="key-name">${escapeHtml(name)}</div>
                <div class="key-value">${escapeHtml(value)}</div>
            </div>
            <div class="key-actions">
                <button class="btn small ghost copy">Копировать</button>
                <button class="btn small danger del">Удалить</button>
            </div>
        `;

        el.querySelector(".copy").addEventListener("click", () => {
            navigator.clipboard.writeText(value);
            toast("Скопировано", "success");
        });

        el.querySelector(".del").addEventListener("click", async () => {
            let url;
            if (type === "aes")       url = `/api/keys/aes/${encodeURIComponent(name)}`;
            else if (type === "time") url = `/api/keys/time/${encodeURIComponent(name)}`;
            else                      url = `/api/keys/num/${idx}`;

            const result = await api(url, { method: "DELETE" });
            if (result.success) {
                toast("Ключ удалён", "info");
                await loadKeys();
            } else {
                toast(result.error || "Ошибка удаления", "error");
            }
        });

        container.appendChild(el);
    });
}

$("#btn-gen-aes").addEventListener("click", () => {
    const bytes = new Uint8Array(32);
    crypto.getRandomValues(bytes);
    $("#aes-key").value = btoa(String.fromCharCode(...bytes));
});

$("#btn-add-aes").addEventListener("click", async () => {
    const name = $("#aes-name").value.trim();
    const key = $("#aes-key").value.trim();
    if (!name || !key) { toast("Введите имя и ключ", "error"); return; }

    const result = await api("/api/keys/aes", {
        method: "POST",
        body: { name, key },
    });
    if (!result.success) {
        toast(result.error || "Ошибка", "error");
        return;
    }
    $("#aes-name").value = "";
    $("#aes-key").value = "";
    toast("Ключ добавлен", "success");
    await loadKeys();
});

$("#btn-gen-salt").addEventListener("click", () => {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    $("#time-salt").value = Array.from(bytes).map(b => b.toString(16).padStart(2, "0")).join("");
});

$("#btn-add-salt").addEventListener("click", async () => {
    const name = $("#time-name").value.trim();
    const salt = $("#time-salt").value.trim();
    if (!name || !salt) { toast("Введите имя и соль", "error"); return; }

    const result = await api("/api/keys/time", {
        method: "POST",
        body: { name, salt },
    });
    if (!result.success) {
        toast(result.error || "Ошибка", "error");
        return;
    }
    $("#time-name").value = "";
    $("#time-salt").value = "";
    toast("Соль добавлена", "success");
    await loadKeys();
});

$("#btn-add-num").addEventListener("click", async () => {
    const key = $("#num-key").value.trim();
    if (!key) { toast("Введите номерной ключ", "error"); return; }

    const result = await api("/api/keys/num", {
        method: "POST",
        body: { key },
    });
    if (!result.success) {
        toast(result.error || "Ошибка", "error");
        return;
    }
    $("#num-key").value = "";
    toast("Ключ добавлен", "success");
    await loadKeys();
});

$("#btn-import-audio").addEventListener("click", () => {
    toast("Импорт из аудио (в разработке)", "info");
});

/* ============================================================
   ПРОЧИЕ КНОПКИ
   ============================================================ */
$("#btn-refresh").addEventListener("click", async () => {
    await loadMessages();
    toast("Обновлено", "info");
});

$("#btn-extract-stego").addEventListener("click", () => {
    const msg = state.selectedMessage;
    if (!msg || !msg.hasStego) {
        toast("В выбранном письме нет скрытых данных", "error");
        return;
    }
    $("#btn-decrypt").click();
});

$("#btn-delete-all").addEventListener("click", () => {
    $("#confirm-title").textContent = "Удаление всей почты";
    $("#confirm-text").textContent = "Вы уверены? Это действие необратимо.";
    openModal("modal-confirm");

    $("#confirm-yes").onclick = async () => {
        const result = await api("/api/messages/delete-all", { method: "POST" });
        if (result.success) {
            state.messages = [];
            state.selectedMessageId = null;
            state.selectedMessage = null;
            hide($("#message-view"));
            show($("#content-empty"));
            renderMessages();
            toast("Все письма удалены", "info");
        } else {
            toast(result.error || "Ошибка удаления", "error");
        }
        closeModal("modal-confirm");
    };
});

/* ============================================================
   INIT
   ============================================================ */
renderComposeAttachments();

const initialCard = document.querySelector(".login-card");
if (initialCard) playCardEnter(initialCard);