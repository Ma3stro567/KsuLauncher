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
            if (text.includes("Ошибка") || text.includes("Запустите") || text.includes("Запуск")) {
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

function add_log(text) { /* Debug disabled */ }

// Initial load
async function init() {
    const settings = await eel.get_settings()();
    if (settings.ram) {
        ramSlider.value = settings.ram;
        ramValue.textContent = `${settings.ram} MB`;
    }
    if (settings.path) {
        document.getElementById('current-path').textContent = settings.path;
    }

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
        document.getElementById('current-path').textContent = path;
        eel.save_settings({ path: path });
    }
});

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

document.getElementById('update-btn').addEventListener('click', () => {
    // Switch to home screen and start installation
    navBtns[0].click();
    playBtn.click();
});

init();
