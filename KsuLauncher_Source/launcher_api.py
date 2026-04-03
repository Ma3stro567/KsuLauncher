import os
import requests
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
import time

VERSIONS_URL = 'https://docs.google.com/spreadsheets/d/1rW6vIDIhrlXweWmcSU3eNVbSrhQjxs346XdkWJlaNUw/export?format=csv'
AUTHLIB_INJECTOR_ID = "1-mYdSVNaz7AkJVzqpBmEtqRxQnGKUBNw"
SERVERS_DAT_ID = "1ojv4-e3R_RA8r2Ngrxg57bT2wac-dHq0"
AUTHLIB_URL = "https://authserver.ely.by"

class LauncherAPI:
    def __init__(self):
        # Global fix: Always use the root of C: to avoid Cyrillic/Admin issues in AppData
        self.minecraft_dir = "C:\\.ksulauncher"
            
        # Ensure directories exist
        try:
            if not os.path.exists(self.minecraft_dir):
                os.makedirs(self.minecraft_dir, exist_ok=True)
        except PermissionError:
            # If C:\ is locked (rare for a folder starting with dot), use a non-Cyrillic fallback
            self.minecraft_dir = os.path.abspath(os.path.join(os.path.expanduser("~"), "KsuLauncher"))
            os.makedirs(self.minecraft_dir, exist_ok=True)

        self.settings_file = os.path.join(self.minecraft_dir, "ksuserver_settings.json")
        self.authlib_injector = os.path.join(self.minecraft_dir, "authlib-injector-1.2.7.jar")
        self.servers_dat = os.path.join(self.minecraft_dir, "servers.dat")
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

    def _download_modpack(self, info, game_dir, report_callback):
        if not info['id_archive']:
            return
            
        mods_dir = os.path.join(game_dir, "mods")
        path_text = game_dir
        output = os.path.join(path_text, "archive.zip")
        
        report_callback("Загрузка модов...", 70)
        gdown.download(id=info['id_archive'], output=output, quiet=True)
        
        if os.path.exists(output):
            report_callback("Распаковка...", 85)
            if os.path.exists(mods_dir): 
                shutil.rmtree(mods_dir)
            with zipfile.ZipFile(output, 'r') as zip_ref:
                zip_ref.extractall(path_text)
            os.remove(output)

    def update_modpack(self, version_name, report_callback):
        try:
            game_dir = self.settings.get("path", self.minecraft_dir)
            info = self.versions_data.get(version_name)
            if not info:
                # Refresh data to be sure
                self.get_versions()
                info = self.versions_data.get(version_name)
                
            if not info:
                report_callback("Ошибка: Версия не найдена", 0)
                return

            self._download_modpack(info, game_dir, report_callback)
            report_callback("Обновление завершено!", 100)
        except Exception as e:
            report_callback(f"Ошибка обновления: {str(e)}", 0)

    def download_and_launch(self, version_name, report_callback, force_update=False):
        try:
            game_dir = os.path.abspath(self.settings.get("path", self.minecraft_dir))
            info = self.versions_data.get(version_name)
            if not info:
                for v in self.versions_data.values():
                    if v.get('minecraft_version') == version_name:
                        info = v; break
            
            if not info:
                report_callback(f"Ошибка: Версия не найдена", 0)
                return

            version_id = f"{info['modloader']}-{info['modloader_version']}"
            version_path = os.path.join(game_dir, "versions", version_id)

            # 1. Minecraft & Runtime (with Retry Logic for [Errno 13] Permission denied)
            if not os.path.exists(version_path):
                report_callback("Установка Minecraft...", 10)
                
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        minecraft_launcher_lib.install.install_minecraft_version(info['minecraft_version'], game_dir)
                        # If success, break the retry loop
                        break
                    except PermissionError as pe:
                        if attempt < max_retries - 1:
                            report_callback(f"Ожидание доступа (попытка {attempt+1}/{max_retries})...", 12)
                            time.sleep(1.5) # Wait for antivirus/system lock
                        else:
                            # Final failure suggest fix
                            err_msg = str(pe)
                            if "Permission denied" in err_msg or "WinError 5" in err_msg:
                                report_callback("ОШИБКА ДОСТУПА: Попробуйте сменить папку игры в Настройках на путь без русских букв (например, C:\\Games\\Ksu).", 0)
                                return
                            raise pe
                
                report_callback("Установка загрузчика...", 40)
                loader = minecraft_launcher_lib.mod_loader.get_mod_loader(info['modloader'])
                dummy_opts = minecraft_launcher_lib.utils.generate_test_options()
                try:
                    vm = minecraft_launcher_lib.command.get_minecraft_command(info['minecraft_version'], game_dir, dummy_opts)
                    java_path = vm[0]
                except: java_path = "java"

                loader.install(info['minecraft_version'], game_dir, loader_version=info['modloader_version'], java=java_path)
            else:
                report_callback("Найден готовый клиент...", 40)

            # 2. Modpack (Smart Start Skip)
            mods_dir = os.path.join(game_dir, "mods")
            if not os.path.exists(mods_dir) or not os.listdir(mods_dir):
                self._download_modpack(info, game_dir, report_callback)
            else:
                report_callback("Клиент готов...", 80)

            # 4. Authlib
            if not os.path.exists(self.authlib_injector):
                report_callback("Загрузка Authlib...", 95)
                gdown.download(id=AUTHLIB_INJECTOR_ID, output=self.authlib_injector, quiet=True)

            # 5. Servers List
            if not os.path.exists(self.servers_dat):
                report_callback("Загрузка серверов...", 98)
                gdown.download(id=SERVERS_DAT_ID, output=self.servers_dat, quiet=True)

            # 6. Launch
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

    def search_modrinth(self, query, version, project_type, page=1, limit=12):
        try:
            offset = (page - 1) * limit
            # Optimized version check
            search_version = version
            if version.count('.') > 1:
                search_version = '.'.join(version.split('.')[:2])

            headers = {"User-Agent": "KsuLauncher/1.2.0 (https://github.com/egorg/KsuLauncher)"}
            
            # project_type can be 'resourcepack' or 'shader'
            base_url = "https://api.modrinth.com/v2/search"
            facets = f'[["project_type:{project_type}"],["versions:{version}"]]'
            
            url = f"{base_url}?query={query}&facets={facets}&offset={offset}&limit={limit}&index=downloads"
            res = requests.get(url, headers=headers, timeout=10)
            
            if res.status_code != 200:
                return {"hits": [], "total_hits": 0, "error": f"Ошибка Modrinth: {res.status_code}"}
                
            data = res.json()
            
            # Final fallback: try base version if 0 results
            if data.get('total_hits', 0) == 0 and search_version != version:
                facets_base = f'[["project_type:{project_type}"],["versions:{search_version}"]]'
                url_base = f"{base_url}?query={query}&facets={facets_base}&offset={offset}&limit={limit}&index=downloads"
                res = requests.get(url_base, headers=headers, timeout=10)
                data = res.json()
                
            return data
        except Exception as e:
            return {"hits": [], "total_hits": 0, "error": f"Сбой сети: {str(e)}"}

    def install_modrinth_project(self, project_id, version, folder_name):
        try:
            headers = {"User-Agent": "KsuLauncher/1.2.0 (https://github.com/egorg/KsuLauncher)"}
            # Find compatible versions
            url = f"https://api.modrinth.com/v2/project/{project_id}/version?game_versions=[\"{version}\"]"
            res = requests.get(url, headers=headers, timeout=10)
            versions = res.json()
            if not versions:
                return {"success": False, "error": "Нет совместимых версий"}
            
            lat = versions[0]
            file_info = next((f for f in lat['files'] if f['primary']), lat['files'][0])
            dl_url = file_info['url']
            fname = file_info['filename']
            
            # Target folder (resourcepacks or shaderpacks)
            game_dir = self.settings.get("path", self.minecraft_dir)
            target_dir = os.path.join(game_dir, folder_name)
            os.makedirs(target_dir, exist_ok=True)
            
            # Download
            dest = os.path.join(target_dir, fname)
            r = requests.get(dl_url, stream=True, timeout=15)
            with open(dest, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return {"success": True, "filename": fname}
        except Exception as e:
            return {"success": False, "error": str(e)}
