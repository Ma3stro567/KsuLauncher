import eel
import os
import sys
import threading
from launcher_api import LauncherAPI

# Resource path for PyInstaller
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

launcher = LauncherAPI()

@eel.expose
def get_versions():
    return launcher.get_versions()

@eel.expose
def login(username, password, totp=None):
    return launcher.login(username, password, totp)

@eel.expose
def get_settings():
    return launcher.load_settings()

@eel.expose
def save_settings(new_settings):
    launcher.save_settings(new_settings)

@eel.expose
def start_launch(version):
    def report(text, p):
        eel.update_status(text, p)()
    threading.Thread(target=launcher.download_and_launch, args=(version, report), daemon=True).start()

@eel.expose
def pick_folder():
    return launcher.pick_folder()

@eel.expose
def open_url(url):
    launcher.open_url(url)

@eel.expose
def logout():
    return launcher.logout()

# Initialize Eel with the web directory
eel.init(resource_path('web'))

print("KsuLauncher started. Two-file architecture restored.")
# Start the app
eel.start('index.html', size=(900, 700))