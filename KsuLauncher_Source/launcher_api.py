import os
import json
import shutil
import threading
import zipfile
import gdown
import minecraft_launcher_lib
import subprocess
import sys
import pandas as pd
import webbrowser
import eel

VERSIONS_URL = 'https://docs.google.com/spreadsheets/d/1rW6vIDIhrlXweWmcSU3eNVbSrhQjxs346XdkWJlaNUw/export?format=csv'
AUTHLIB_INJECTOR_ID = "1-mYdSVNaz7AkJVzqpBmEtqRxQnGKUBNw"
AUTHLIB_URL = "https://authserver.ely.by"

class LauncherAPI:
    def __init__(self):
        self.minecraft_dir = os.path.join(os.getenv("APPDATA"), ".ksulauncher")
        os.makedirs(self.minecraft_dir, exist_ok=True)
        self.settings_file = os.path.join(self.minecraft_dir, "ksuserver_settings.json")
        self.authlib_injector = os.path.join(self.minecraft_dir, "authlib-injector-1.2.7.jar")
        self.versions_data = {}
        self.current_user = None
        self.settings = self.load_settings()
        
        if not os.path.exists(self.settings_file):
            self.save_settings(self.settings)

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return {"path": self.minecraft_dir, "ram": 4096}

    def save_settings(self, new_settings):
        self.settings.update(new_settings)
        with open(self.settings_file, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, indent=2)

    def get_versions(self):
        try:
            df_local = pd.read_csv(VERSIONS_URL)
            version_list = []
            self.versions_data = {}
            for idx, row in df_local.iterrows():
                v_name = str(row.iloc[0])
                version_list.append(v_name)
                v_info = {
                    'name': str(row.iloc[0]),
                    'modloader': row.iloc[1] if pd.notna(row.iloc[1]) else 'neoforge',
                    'minecraft_version': row.iloc[2] if pd.notna(row.iloc[2]) else '1.21.1',
                    'modloader_version': row.iloc[3] if pd.notna(row.iloc[3]) else '21.1.221',
                    'id_archive': row.iloc[4] if pd.notna(row.iloc[4]) else '',
                    'serv_entry': row.iloc[5] if pd.notna(row.iloc[5]) else ''
                }
                self.versions_data[v_name] = v_info
            return version_list
        except: return []

    def login(self, username, password, totp=None):
        import uuid
        import requests
        auth_pass = f"{password}:{totp}" if totp else password
        payload = {"username": username, "password": auth_pass, "requestUser": True, "clientToken": str(uuid.uuid4())}
        try:
            response = requests.post("https://authserver.ely.by/auth/authenticate", json=payload, timeout=15)
            if response.status_code == 200:
                data = response.json()
                self.current_user = {
                    "username": data["selectedProfile"]["name"],
                    "uuid": data["selectedProfile"]["id"],
                    "access_token": data["accessToken"]
                }
                self.save_settings({"username": username, "password": password})
                return {"success": True, "username": self.current_user["username"]}
            else:
                try: err_msg = response.json().get("errorMessage", "Ошибка входа")
                except: err_msg = "Ошибка сервера"
                return {"success": False, "error": err_msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def download_and_launch(self, version_name, report_callback):
        try:
            game_dir = self.settings.get("path", self.minecraft_dir)
            info = self.versions_data.get(version_name)
            if not info:
                for v in self.versions_data.values():
                    if v.get('minecraft_version') == version_name:
                        info = v; break
            
            if not info:
                report_callback(f"Ошибка: Версия не найдена", 0)
                return

            # 1. Minecraft
            report_callback("Проchecking Minecraft...", 10)
            minecraft_launcher_lib.install.install_minecraft_version(info['minecraft_version'], game_dir)
            
            # 2. Loader
            report_callback("Установка загрузчика...", 40)
            loader = minecraft_launcher_lib.mod_loader.get_mod_loader(info['modloader'])
            dummy_opts = minecraft_launcher_lib.utils.generate_test_options()
            try:
                vm = minecraft_launcher_lib.command.get_minecraft_command(info['minecraft_version'], game_dir, dummy_opts)
                java_path = vm[0]
            except: java_path = "java"

            loader.install(info['minecraft_version'], game_dir, loader_version=info['modloader_version'], java=java_path)

            # 3. Modpack
            if info['id_archive']:
                path_text = game_dir
                output = os.path.join(path_text, "archive.zip")
                report_callback("Загрузка модов...", 70)
                gdown.download(id=info['id_archive'], output=output, quiet=True)
                
                if os.path.exists(output):
                    mods_dir = os.path.join(path_text, "mods")
                    if os.path.exists(mods_dir): shutil.rmtree(mods_dir)
                    with zipfile.ZipFile(output, 'r') as zip_ref:
                        zip_ref.extractall(path_text)
                    os.remove(output)

            # 4. Authlib
            if not os.path.exists(self.authlib_injector):
                report_callback("Загрузка Authlib...", 95)
                gdown.download(id=AUTHLIB_INJECTOR_ID, output=self.authlib_injector, quiet=True)

            # 5. Launch
            report_callback("Запуск игры!", 100)
            version_id = f"{info['modloader']}-{info['modloader_version']}"
            options = {
                "username": self.current_user["username"] if self.current_user else "Player",
                "uuid": self.current_user["uuid"] if self.current_user else "uuid",
                "token": self.current_user["access_token"] if self.current_user else "token",
                "jvmArguments": [f"-javaagent:{self.authlib_injector}={AUTHLIB_URL}", "-Dauthlibinjector.noLogFile", f"-Xmx{self.settings.get('ram', 4096)}M"]
            }
            cmd = minecraft_launcher_lib.command.get_minecraft_command(version_id, game_dir, options)
            proc = subprocess.Popen(cmd, cwd=game_dir, creationflags=subprocess.CREATE_NO_WINDOW)
            threading.Thread(target=lambda: proc.wait(), daemon=True).start()
            
        except Exception as e:
            report_callback(f"Ошибка: {str(e)}", 0)

    def pick_folder(self):
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
        path = filedialog.askdirectory(initialdir=self.minecraft_dir)
        root.destroy()
        return path.replace("/", "\\") if path else None

    def open_url(self, url):
        webbrowser.open(url)

    def logout(self):
        self.save_settings({"username": "", "password": ""})
        self.current_user = None
        return True
