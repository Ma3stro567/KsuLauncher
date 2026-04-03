// Tab Switching Logic
const navBtns = document.querySelectorAll('.nav-btn');
const screens = document.querySelectorAll('.screen');

navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const target = btn.dataset.target;

        navBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        screens.forEach(s => {
            s.classList.remove('active');
            if (s.id === target) s.classList.add('active');
        });
    });
});

// RAM Slider logic
const ramSlider = document.getElementById('ram-slider');
const ramValue = document.getElementById('ram-value');

ramSlider.addEventListener('input', (e) => {
    const val = e.target.value;
    ramValue.textContent = `${val} MB`;
    eel.save_settings({ ram: parseInt(val) });
});

// Window controls
document.getElementById('close-btn').addEventListener('click', () => {
    window.close(); // Or eel.close_app()
});

document.getElementById('minimize-btn').addEventListener('click', () => {
    eel.minimize_window();
});

// Play logic
const playBtn = document.getElementById('play-btn');
const statusText = document.getElementById('status-text');
const progressBar = document.getElementById('progress-bar');
const loginOverlay = document.getElementById('login-overlay');

let currentVersion = '1.21.1';

playBtn.addEventListener('click', async () => {
    if (playBtn.classList.contains('disabled')) return;

    // Check if logged in
    const settings = await eel.get_settings()();
    if (!settings.username || !settings.password) {
        showLogin();
        return;
    }

    playBtn.classList.add('disabled');
    playBtn.style.opacity = '0.5';
    statusText.textContent = "Инициализация...";
    progressBar.style.width = '5%';

    // Start installation/launch process
    eel.start_launch(currentVersion);
});

// Login UI handlers
function showLogin() {
    loginOverlay.classList.remove('hidden');
}

const loginBtn = document.getElementById('login-btn');
loginBtn.addEventListener('click', async () => {
    const email = document.getElementById('email-input').value;
    const pass = document.getElementById('pass-input').value;
    const totp = document.getElementById('totp-input') ? document.getElementById('totp-input').value : null;

    if (!email || !pass) {
        alert('Введите почту и пароль!');
        return;
    }

    loginBtn.textContent = 'Входим...';
    loginBtn.style.opacity = '0.5';

    add_log(`Попытка входа: ${email}`);
    // If TOTP is visible/exists, pass it too
    const result = await eel.login(email, pass, totp)();

    if (result.success) {
        add_log(`Вход выполнен: ${result.username}`);
        loginOverlay.classList.add('hidden');
        statusText.textContent = `Привет, ${result.username}!`;
    } else {
        add_log(`Ошибка входа: ${result.error}`);
        alert(result.error);
        loginBtn.textContent = 'ВОЙТИ В АККАУНТ';
        loginBtn.style.opacity = '1';
    }
});

// Expose functions to Python
eel.expose(update_status);
function update_status(text, progress = null) {
    if (text) {
        add_log(`[STATUS] ${text}`);
        statusText.style.opacity = '0';
        setTimeout(() => {
            statusText.textContent = text;
            statusText.style.opacity = '1';

            // Re-enable button on error or final step
            const lowerText = text.toLowerCase();
            if (lowerText.includes("ошибка") || text.includes("Запустите") || text.includes("Запуск")) {
                playBtn.classList.remove('disabled');
                playBtn.style.opacity = '1';
            }
        }, 150);
    }
    if (progress !== null) {
        progressBar.style.width = `${progress}%`;
        if (progress >= 100) {
            playBtn.classList.remove('disabled');
            playBtn.style.opacity = '1';
        }
    }
}

eel.expose(add_log);
function add_log(text) {
    const logContainer = document.getElementById('status-log');
    if (!logContainer) return;

    const logLine = document.createElement('div');
    logLine.className = 'log-line';

    const time = new Date().toLocaleTimeString();
    logLine.innerHTML = `<span class="log-time">[${time}]</span> <span class="log-text">${text}</span>`;

    logContainer.appendChild(logLine);
    logContainer.scrollTop = logContainer.scrollHeight;

    if (logContainer.childNodes.length > 50) {
        logContainer.removeChild(logContainer.firstChild);
    }
}

// Initial load
async function init() {
    const settings = await eel.get_settings()();
    if (settings.ram) {
        ramSlider.value = settings.ram;
        ramValue.textContent = `${settings.ram} MB`;
    }
    const pathInput = document.getElementById('current-path');
    if (settings.path) {
        pathInput.value = settings.path;
    }

    // Save manually edited path
    pathInput.onchange = () => {
        const newPath = pathInput.value.trim();
        if (newPath) {
            eel.save_settings({ path: newPath });
            add_log(`Путь вручную изменен на: ${newPath}`);
        }
    };

    // Pre-load versions in background
    eel.get_versions()();

    // Delay autologin slightly to ensure stable connection
    setTimeout(async () => {
        if (settings.username && settings.password) {
            update_status("Авто-логин...", 5);
            add_log("Попытка автологина...");
            const result = await eel.login(settings.username, settings.password)();
            if (result.success) {
                add_log(`Автологин успешен: ${result.username}`);
                onLoginSuccess(result.username);
            } else {
                add_log(`Автологин не удался: ${result.error}`);
                update_status("");
                showLogin();
            }
        } else {
            showLogin();
        }
    }, 1000);
}

document.getElementById('browse-btn').addEventListener('click', async () => {
    const path = await eel.pick_folder()();
    if (path) {
        document.getElementById('current-path').value = path;
        eel.save_settings({ path: path });
        add_log(`Путь изменен через обзор: ${path}`);
    }
});

// Update Modpack Button
const updateBtn = document.getElementById('update-btn');
if (updateBtn) {
    updateBtn.addEventListener('click', () => {
        if (updateBtn.classList.contains('disabled')) return;
        
        updateBtn.classList.add('disabled');
        updateBtn.textContent = "ЗАГРУЗКА...";
        add_log("Запуск принудительного обновления модпака...");
        eel.update_modpack(currentVersion);
        
        // Reset button after some time or via a status check
        // For now, we'll let the user wait for the status text to finish
        setTimeout(() => {
            updateBtn.classList.remove('disabled');
            updateBtn.textContent = "УСТАНОВИТЬ ОБНОВЛЕНИЕ";
        }, 10000); // 10s cooldown/buffer
    });
}

// Logout Logic
const logoutModal = document.getElementById('logout-modal');
const logoutBtn = document.getElementById('logout-btn');
const confirmLogout = document.getElementById('confirm-logout');
const cancelLogout = document.getElementById('cancel-logout');

logoutBtn.addEventListener('click', () => {
    logoutModal.classList.remove('hidden');
});

cancelLogout.addEventListener('click', () => {
    logoutModal.classList.add('hidden');
});

confirmLogout.addEventListener('click', async () => {
    logoutModal.classList.add('hidden');
    // Clear tokens from memory and file
    await eel.save_settings({ username: "", password: "" })();
    loginOverlay.classList.remove('hidden');
    statusText.textContent = "Войдите в аккаунт";
    // Reset inputs
    document.getElementById('email-input').value = "";
    document.getElementById('pass-input').value = "";
});

// External links
document.getElementById('reg-link').onclick = () => eel.open_url('https://account.ely.by/register');

// Modrinth Content Logic
let currentRPPage = 1;
let currentRPQuery = '';
let currentModrinthType = 'resourcepack'; // or 'shader'
const RP_LIMIT = 12;

const rpSearchInput = document.getElementById('rp-search-input');
const rpGrid = document.getElementById('rp-grid');
const rpPagination = document.getElementById('rp-pagination');
const subTabs = document.querySelectorAll('.sub-tab');

// Tab switching inside search screen
subTabs.forEach(tab => {
    tab.onclick = () => {
        if (tab.classList.contains('active')) return;
        
        subTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        
        currentModrinthType = tab.dataset.type;
        currentRPPage = 1;
        loadResourcePacks();
    };
});

// Debounce for search
let searchTimeout;
if (rpSearchInput) {
    rpSearchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            currentRPQuery = e.target.value;
            currentRPPage = 1;
            loadResourcePacks();
        }, 500);
    });
}

async function loadResourcePacks() {
    if (!rpGrid) return;
    
    add_log(`Загрузка ${currentModrinthType === 'shader' ? 'шейдеров' : 'ресурспаков'}...`);
    rpGrid.innerHTML = '<div class="status-msg">Синхронизация базы Modrinth...</div>';
    rpPagination.innerHTML = '';

    const gameVersion = currentVersion || '1.21.1';

    // Fetch from backend
    const result = await eel.search_modrinth(currentRPQuery, gameVersion, currentModrinthType, currentRPPage)();
    
    if (result.error) {
        rpGrid.innerHTML = `<div class="status-msg" style="color: #ef4444;">Ошибка: ${result.error}</div>`;
        return;
    }

    renderRPPagination(result.total_hits || 0);

    if (!result.hits || result.hits.length === 0) {
        rpGrid.innerHTML = '<div class="status-msg">Ничего не найдено :( Попробуйте другой запрос или смените вкладку.</div>';
        return;
    }

    renderRPCards(result.hits);
}

function renderRPCards(hits) {
    rpGrid.innerHTML = '';
    hits.forEach(hit => {
        const card = document.createElement('div');
        card.className = 'rp-card glass';
        
        // Smarter download formatting
        let downloads = hit.downloads;
        if (downloads >= 1000000) {
            downloads = (downloads / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
        } else if (downloads >= 1000) {
            downloads = (downloads / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
        }
        
        card.innerHTML = `
            <img src="${hit.icon_url || 'https://placehold.co/400x400?text=No+Icon'}" class="rp-thumb" alt="${hit.title}">
            <div class="rp-info">
                <h3 title="${hit.title}">${hit.title}</h3>
                <p title="${hit.description}">${hit.description}</p>
            </div>
            <div class="rp-meta">
                <span title="Скачиваний">📥 ${downloads}</span>
                <button class="primary-btn install-btn" data-id="${hit.project_id}" style="padding: 8px 15px; font-size: 0.7rem;">Установить</button>
            </div>
        `;
        
        const installBtn = card.querySelector('.install-btn');
        installBtn.onclick = async () => {
            installBtn.textContent = '...';
            installBtn.classList.add('disabled');
            
            // Determine target folder
            const folder = currentModrinthType === 'shader' ? 'shaderpacks' : 'resourcepacks';
            
            const res = await eel.install_modrinth(hit.project_id, currentVersion, folder)();
            if (res.success) {
                installBtn.textContent = 'ГОТОВО!';
                installBtn.style.background = '#22c55e';
                add_log(`${currentModrinthType === 'shader' ? 'Шейдер' : 'Пак'} установлен: ${res.filename}`);
            } else {
                installBtn.textContent = 'ОШИБКА';
                installBtn.style.background = '#ef4444';
                add_log(`Ошибка: ${res.error}`);
                setTimeout(() => {
                    installBtn.textContent = 'Установить';
                    installBtn.style.background = '';
                    installBtn.classList.remove('disabled');
                }, 2000);
            }
        };
        
        rpGrid.appendChild(card);
    });
}

function renderRPPagination(totalHits) {
    rpPagination.innerHTML = '';
    const totalPages = Math.min(Math.ceil(totalHits / RP_LIMIT), 20); // Cap at 20 pages for stability
    if (totalPages <= 1) return;

    const maxVisible = 5;
    let startPage = Math.max(1, currentRPPage - 2);
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);
    
    if (endPage - startPage < maxVisible - 1) {
        startPage = Math.max(1, endPage - maxVisible + 1);
    }

    for (let i = startPage; i <= endPage; i++) {
        const btn = document.createElement('button');
        btn.className = `page-btn ${i === currentRPPage ? 'active' : ''}`;
        btn.textContent = i;
        btn.onclick = () => {
            if (currentRPPage === i) return;
            currentRPPage = i;
            loadResourcePacks();
            // Scroll content to top
            document.querySelector('.content').scrollTop = 0;
        };
        rpPagination.appendChild(btn);
    }
}

// Trigger load on screen switch
navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        if (btn.getAttribute('data-target') === 'rp-screen') {
            loadResourcePacks();
        }
    });
});

function onLoginSuccess(username) {
    statusText.textContent = `Привет, ${username}!`;
    update_status("Готов к запуску");
    add_log(`Вход выполнен: ${username}`);
}

init();
