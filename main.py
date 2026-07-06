#!/usr/bin/env python3
"""
Автономный Git-управляемый сервер автоматизации для Windows.
Все результаты сохраняются в RESULTS.md для удаленного мониторинга.
"""

import os
import sys
import time
import json
import subprocess
import threading
import hashlib
import locale
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple

import git
from mss import mss
from PIL import Image
import pyautogui

# Определяем системную кодировку
SYSTEM_ENCODING = locale.getpreferredencoding()

# Настройки путей - всё в текущей директории
REPO_PATH = Path(".")
COMMANDS_FILE = REPO_PATH / "commands.txt"
INPUTS_FILE = REPO_PATH / "inputs.txt"
RESULTS_FILE = REPO_PATH / "RESULTS.md"
SCREENSHOTS_DIR = REPO_PATH / "screenshots"
LOGS_DIR = REPO_PATH / "logs"

# Блокировки
command_lock = threading.Lock()
EXECUTED_COMMANDS_FILE = REPO_PATH / ".executed_commands"
MAX_SCREENSHOT_COMMITS = 5

# Настройка pyautogui
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.1


class AutomationServer:
    """Автономный сервер автоматизации."""
    
    def __init__(self, repo_url: Optional[str] = None):
        self.repo_url = repo_url
        self.repo = None
        self.start_time = datetime.now()
        self.commands_executed = 0
        self.screenshots_taken = 0
        self.inputs_processed = 0
        self.errors_count = 0
        self.last_activity = "Запуск сервера"
        self.current_status = "RUNNING"
        self.last_status_print = time.time()
        self.setup_environment()
        self.init_results_file()
        
    def init_results_file(self):
        """Инициализация файла результатов."""
        if not RESULTS_FILE.exists():
            RESULTS_FILE.write_text(
                "# Результаты выполнения команд\n\n"
                f"**Сервер запущен:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                "---\n\n",
                encoding='utf-8'
            )
    
    def safe_read_file(self, file_path: Path) -> str:
        """Безопасное чтение файла с автоопределением кодировки."""
        if not file_path.exists():
            return ""
        
        encodings = ['utf-8', 'utf-8-sig', SYSTEM_ENCODING, 'cp1251', 'cp866', 'latin-1']
        
        for encoding in encodings:
            try:
                content = file_path.read_text(encoding=encoding)
                if encoding != 'utf-8':
                    file_path.write_text(content, encoding='utf-8')
                return content
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        raw_data = file_path.read_bytes()
        return raw_data.decode('utf-8', errors='replace')
    
    def setup_environment(self):
        """Настройка окружения в текущей директории."""
        SCREENSHOTS_DIR.mkdir(exist_ok=True)
        LOGS_DIR.mkdir(exist_ok=True)
        
        if not COMMANDS_FILE.exists():
            COMMANDS_FILE.write_text(
                "# Команды для выполнения\n# get_screenshot - создать скриншот\n\n",
                encoding='utf-8'
            )
        
        if not INPUTS_FILE.exists():
            INPUTS_FILE.write_text(
                "# Команды ввода\n# Формат:\n# type: click\n# coordinates: [0.5, 0.5]\n# button: left\n\n",
                encoding='utf-8'
            )
        
        if not EXECUTED_COMMANDS_FILE.exists():
            EXECUTED_COMMANDS_FILE.write_text("", encoding='utf-8')
        
        try:
            self.repo = git.Repo(REPO_PATH)
        except git.InvalidGitRepositoryError:
            self.repo = git.Repo.init(REPO_PATH)
            with self.repo.config_writer() as config:
                config.set_value("user", "name", "Automation Server")
                config.set_value("user", "email", "server@automation.local")
            
            gitignore_path = REPO_PATH / ".gitignore"
            if not gitignore_path.exists():
                gitignore_path.write_text(
                    "*.pyc\n__pycache__/\n.DS_Store\n*.tmp\nlogs/status.log\n.executed_commands\n",
                    encoding='utf-8'
                )
            
            self.repo.index.add(['.gitignore', 'commands.txt', 'inputs.txt', 'RESULTS.md'])
            self.repo.index.commit("Initial commit")
    
    def add_to_results(self, entry_type: str, command: str, result: str, success: bool):
        """Добавление записи в RESULTS.md."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_icon = "OK" if success else "ERROR"
        status_text = "Успешно" if success else "Ошибка"
        
        if entry_type == "command":
            header = f"### {status_icon} Команда - {timestamp}"
        elif entry_type == "screenshot":
            header = f"### SCREENSHOT - {timestamp}"
        elif entry_type == "input":
            header = f"### INPUT - {timestamp}"
        else:
            header = f"### {timestamp}"
        
        if len(result) > 1000:
            result = result[:997] + "..."
        
        entry = f"\n{header}\n\n"
        entry += f"**Команда:** `{command}`\n"
        entry += f"**Статус:** {status_text}\n\n"
        entry += f"```\n{result}\n```\n\n---\n"
        
        try:
            if RESULTS_FILE.exists():
                old_content = RESULTS_FILE.read_text(encoding='utf-8')
                header_end = old_content.find("---\n\n")
                if header_end != -1:
                    header_end += 5
                    new_content = old_content[:header_end] + entry + old_content[header_end:]
                else:
                    new_content = entry + old_content
            else:
                new_content = f"# Результаты выполнения команд\n\n**Сервер запущен:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n{entry}"
            
            RESULTS_FILE.write_text(new_content, encoding='utf-8')
            
        except Exception as e:
            print(f"Warning: Cannot write to RESULTS.md: {e}")
    
    def print_status(self):
        """Вывод статуса в консоль."""
        uptime = datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0]
        
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    СТАТУС СЕРВЕРА АВТОМАТИЗАЦИИ               ║
╠══════════════════════════════════════════════════════════════╣
║ Статус:          {self.current_status:<43}║
║ Запуск:          {self.start_time.strftime('%H:%M:%S'):<43}║
║ Аптайм:          {uptime_str:<43}║
║ Текущее время:   {datetime.now().strftime('%H:%M:%S'):<43}║
╠══════════════════════════════════════════════════════════════╣
║ Выполнено команд:     {self.commands_executed:<36}║
║ Создано скриншотов:   {self.screenshots_taken:<36}║
║ Обработано вводов:    {self.inputs_processed:<36}║
║ Ошибок:               {self.errors_count:<36}║
╠══════════════════════════════════════════════════════════════╣
║ Последняя активность:                                      ║
║ {self.last_activity[:60]:<60}║
╚══════════════════════════════════════════════════════════════╝

commands.txt | inputs.txt | RESULTS.md | screenshots/
Enter command or 'help':""", end=' ', flush=True)
    
    def pull_changes(self):
        """Получение изменений из Git."""
        if self.repo_url:
            try:
                origin = self.repo.remotes.origin
                origin.pull()
            except Exception:
                pass
    
    def push_changes(self, message: str = "Automated commit"):
        """Отправка изменений в Git."""
        try:
            self.repo.index.add(['RESULTS.md', 'commands.txt', 'inputs.txt'])
            self.repo.index.add(['screenshots/*.png'])
            
            if self.repo.is_dirty() or self.repo.untracked_files:
                self.repo.index.commit(message)
                if self.repo_url:
                    self.repo.remotes.origin.push()
        except Exception:
            pass
    
    def read_commands(self) -> List[str]:
        """Чтение команд из файла."""
        content = self.safe_read_file(COMMANDS_FILE)
        commands = []
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                commands.append(line)
        return commands
    
    def get_executed_commands(self) -> set:
        """Получение выполненных команд."""
        content = self.safe_read_file(EXECUTED_COMMANDS_FILE)
        return set(filter(None, content.splitlines()))
    
    def mark_command_executed(self, command: str):
        """Отметка команды как выполненной."""
        cmd_hash = hashlib.md5(command.encode('utf-8')).hexdigest()
        with open(EXECUTED_COMMANDS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{cmd_hash}\n")
    
    def take_screenshot(self) -> Tuple[bool, str]:
        """Создание скриншота экрана."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"screenshot_{timestamp}.png"
            screenshot_path = SCREENSHOTS_DIR / filename
            
            print(f"\nCreating screenshot...")
            
            with mss() as sct:
                sct.shot(output=str(screenshot_path))
            
            img = Image.open(screenshot_path)
            img.save(screenshot_path, optimize=True, quality=85)
            
            size_mb = screenshot_path.stat().st_size / (1024 * 1024)
            self.screenshots_taken += 1
            
            self.cleanup_old_screenshots()
            
            success_msg = f"Screenshot created: {filename} ({size_mb:.2f} MB)"
            print(f"OK {success_msg}")
            
            self.last_activity = f"Screenshot: {filename}"
            
            self.add_to_results("screenshot", "get_screenshot", 
                              f"Screenshot: {filename}\nSize: {size_mb:.2f} MB\nPath: screenshots/{filename}", 
                              True)
            
            return True, success_msg
            
        except Exception as e:
            self.errors_count += 1
            error_msg = f"Screenshot error: {str(e)}"
            print(f"ERROR {error_msg}")
            
            self.add_to_results("screenshot", "get_screenshot", error_msg, False)
            
            return False, error_msg
    
    def cleanup_old_screenshots(self):
        """Удаление старых скриншотов."""
        try:
            screenshots = sorted(
                SCREENSHOTS_DIR.glob("screenshot_*.png"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            if len(screenshots) > MAX_SCREENSHOT_COMMITS:
                for old_file in screenshots[MAX_SCREENSHOT_COMMITS:]:
                    old_file.unlink()
        except Exception:
            pass
    
    def execute_command(self, command: str) -> Tuple[bool, str]:
        """Выполнение команды в терминале."""
        try:
            if command.strip().lower() == "get_screenshot":
                return self.take_screenshot()
            
            print(f"\nExecuting: {command}")
            
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,
                encoding=SYSTEM_ENCODING,
                errors='replace'
            )
            
            output = result.stdout + result.stderr
            
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr)
            
            success = result.returncode == 0
            
            self.commands_executed += 1
            self.last_activity = f"Command: {command[:50]}"
            
            if success:
                print("OK")
            else:
                self.errors_count += 1
                print(f"ERROR (code {result.returncode})")
            
            self.add_to_results("command", command, output if output else "(no output)", success)
            
            return success, output
            
        except subprocess.TimeoutExpired:
            self.errors_count += 1
            error_msg = "Timeout (300s)"
            print(f"ERROR {error_msg}")
            self.add_to_results("command", command, error_msg, False)
            return False, error_msg
        except Exception as e:
            self.errors_count += 1
            error_msg = f"Error: {str(e)}"
            print(f"ERROR {error_msg}")
            self.add_to_results("command", command, error_msg, False)
            return False, error_msg
    
    def read_inputs(self) -> List[Dict]:
        """Чтение команд ввода из файла."""
        content = self.safe_read_file(INPUTS_FILE)
        inputs = []
        current_input = {}
        
        for line in content.splitlines():
            line = line.strip()
            
            if not line or line.startswith('#'):
                if current_input:
                    inputs.append(current_input)
                    current_input = {}
                continue
            
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == 'type' and value in ['click', 'keyboard', 'delay', 'screenshot']:
                    if current_input:
                        inputs.append(current_input)
                    current_input = {'type': value}
                elif key == 'coordinates':
                    value = value.strip('[]')
                    try:
                        x, y = map(float, value.split(','))
                        current_input['x'] = x
                        current_input['y'] = y
                    except:
                        pass
                elif key == 'button':
                    current_input['button'] = value
                elif key == 'keys':
                    current_input['keys'] = value
                elif key == 'duration':
                    try:
                        current_input['duration'] = float(value)
                    except:
                        pass
        
        if current_input:
            inputs.append(current_input)
        
        return inputs
    
    def execute_input(self, input_data: Dict) -> Tuple[bool, str]:
        """Выполнение команды ввода."""
        try:
            input_type = input_data.get('type')
            
            if input_type == 'screenshot':
                return self.take_screenshot()
            
            elif input_type == 'delay':
                duration = input_data.get('duration', 0.5)
                print(f"Delay {duration}s...")
                time.sleep(duration)
                msg = f"Delay {duration}s"
                self.add_to_results("input", "delay", msg, True)
                return True, msg
            
            elif input_type == 'click':
                screen_width, screen_height = pyautogui.size()
                x = int(input_data['x'] * screen_width)
                y = int(input_data['y'] * screen_height)
                button = input_data.get('button', 'left')
                
                print(f"Click ({x}, {y}) - {button}")
                pyautogui.click(x, y, button=button)
                msg = f"Click ({x}, {y}) - {button}"
                self.add_to_results("input", f"click [{input_data['x']}, {input_data['y']}]", msg, True)
                return True, msg
            
            elif input_type == 'keyboard':
                keys = input_data.get('keys', '')
                print(f"Keys: {keys}")
                
                if '+' in keys:
                    pyautogui.hotkey(*keys.split('+'))
                else:
                    pyautogui.typewrite(keys)
                
                msg = f"Keys: {keys}"
                self.add_to_results("input", "keyboard", msg, True)
                return True, msg
            
            return False, f"Unknown type: {input_type}"
            
        except Exception as e:
            error_msg = f"Input error: {str(e)}"
            self.add_to_results("input", str(input_data), error_msg, False)
            return False, error_msg
    
    def process_inputs(self):
        """Обработка команд ввода."""
        try:
            inputs = self.read_inputs()
            if not inputs:
                return
            
            print(f"\nProcessing {len(inputs)} input commands:")
            
            results_summary = []
            for i, input_data in enumerate(inputs, 1):
                success, message = self.execute_input(input_data)
                status = "OK" if success else "ERROR"
                print(f"  {i}. {status} {message}")
                results_summary.append(f"{i}. {status} {message}")
                if not success:
                    self.errors_count += 1
            
            self.inputs_processed += len(inputs)
            self.last_activity = f"Processed {len(inputs)} inputs"
            
            summary = "\n".join(results_summary)
            self.add_to_results("input", f"Batch of {len(inputs)} commands", summary, True)
            
            INPUTS_FILE.write_text(
                "# Commands input\n# Format:\n# type: click\n# coordinates: [0.5, 0.5]\n# button: left\n\n",
                encoding='utf-8'
            )
            
        except Exception as e:
            self.errors_count += 1
            print(f"ERROR processing inputs: {e}")
    
    def show_help(self):
        """Показ справки."""
        print("""
╔══════════════════════════════════════════════════════════════╗
║                    AVAILABLE COMMANDS                        ║
╠══════════════════════════════════════════════════════════════╣
║ screen, scr     - Take screenshot                           ║
║ status, st      - Show status                               ║
║ exec, run [cmd] - Execute console command                   ║
║   Example: exec dir                                        ║
║   Example: exec echo Hello                                 ║
║ click [x] [y]   - Mouse click (0.0-1.0 coordinates)        ║
║   Example: click 0.5 0.5  (center)                         ║
║   Example: click 0.1 0.1  (top-left)                       ║
║ type [text]     - Type text                                ║
║   Example: type Hello world!                               ║
║ hotkey [keys]   - Press key combination                    ║
║   Example: hotkey ctrl+c                                   ║
║   Example: hotkey alt+tab                                  ║
║ results         - Show RESULTS.md content                  ║
║ help, ?         - Show this help                           ║
║ quit, exit      - Exit                                     ║
║                                                             ║
║ Server checks commands.txt and inputs.txt                  ║
║ All results saved to RESULTS.md                            ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    def handle_user_input(self, user_input: str):
        """Обработка пользовательского ввода из консоли."""
        parts = user_input.strip().split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd in ['screen', 'scr']:
            self.take_screenshot()
        elif cmd in ['status', 'st']:
            self.last_status_print = 0
        elif cmd in ['exec', 'run']:
            if args:
                self.execute_command(args)
                self.commands_executed += 1
            else:
                print("ERROR: Specify command. Example: exec dir")
        elif cmd == 'click':
            try:
                coords = args.split()
                if len(coords) == 2:
                    x, y = float(coords[0]), float(coords[1])
                    screen_w, screen_h = pyautogui.size()
                    click_x = int(x * screen_w)
                    click_y = int(y * screen_h)
                    print(f"Click ({click_x}, {click_y})")
                    pyautogui.click(click_x, click_y)
                    self.inputs_processed += 1
                    self.last_activity = f"Click ({click_x}, {click_y})"
                    self.add_to_results("input", f"click {x} {y}", 
                                      f"Click ({click_x}, {click_y})", True)
                else:
                    print("ERROR: Format: click X Y (e.g.: click 0.5 0.5)")
            except ValueError:
                print("ERROR: Coordinates must be numbers")
        elif cmd == 'type':
            if args:
                print(f"Typing: {args}")
                pyautogui.typewrite(args)
                self.inputs_processed += 1
                self.last_activity = "Text input"
                self.add_to_results("input", "type", f"Text: {args}", True)
            else:
                print("ERROR: Specify text. Example: type Hello")
        elif cmd == 'hotkey':
            if args:
                keys = args.replace(' ', '').split('+')
                print(f"Hotkey: {'+'.join(keys)}")
                pyautogui.hotkey(*keys)
                self.inputs_processed += 1
                self.last_activity = f"Hotkey: {'+'.join(keys)}"
                self.add_to_results("input", "hotkey", f"Combination: {'+'.join(keys)}", True)
            else:
                print("ERROR: Specify keys. Example: hotkey ctrl+c")
        elif cmd == 'results':
            if RESULTS_FILE.exists():
                print("\n" + "="*60)
                print("RESULTS.md content:")
                print("="*60)
                print(RESULTS_FILE.read_text(encoding='utf-8'))
            else:
                print("RESULTS.md not created yet")
        elif cmd in ['help', '?']:
            self.show_help()
        elif cmd in ['quit', 'exit']:
            self.current_status = "STOPPING"
            print("\nShutting down...")
            self.add_to_results("system", "shutdown", "Server stopped by user", True)
            self.push_changes("Server stopped")
            sys.exit(0)
        elif cmd:
            self.execute_command(user_input)
            self.commands_executed += 1
        
        if cmd not in ['status', 'st', 'quit', 'exit']:
            input("\nPress Enter to continue...")
    
    def run(self, check_interval: int = 5):
        """Главный цикл сервера."""
        self.print_status()
        
        def file_checker():
            while self.current_status == "RUNNING":
                with command_lock:
                    self.pull_changes()
                    
                    commands = self.read_commands()
                    executed = self.get_executed_commands()
                    
                    new_commands = []
                    for cmd in commands:
                        cmd_hash = hashlib.md5(cmd.encode('utf-8')).hexdigest()
                        if cmd_hash not in executed:
                            new_commands.append(cmd)
                    
                    if new_commands:
                        print(f"\nFound {len(new_commands)} new commands in file")
                        for cmd in new_commands:
                            self.execute_command(cmd)
                            self.mark_command_executed(cmd)
                        self.push_changes(f"Executed {len(new_commands)} commands")
                        print("\nPress Enter to continue...")
                    
                    if INPUTS_FILE.exists():
                        content = self.safe_read_file(INPUTS_FILE)
                        has_commands = any(
                            line.strip() and not line.strip().startswith('#') 
                            for line in content.splitlines()
                        )
                        if has_commands:
                            print("\nFound input commands in file")
                            self.process_inputs()
                            self.push_changes("Processed inputs")
                            print("\nPress Enter to continue...")
                
                time.sleep(check_interval)
        
        checker_thread = threading.Thread(target=file_checker, daemon=True)
        checker_thread.start()
        
        while self.current_status == "RUNNING":
            if time.time() - self.last_status_print > 2:
                self.print_status()
                self.last_status_print = time.time()
            
            try:
                import msvcrt
                if msvcrt.kbhit():
                    user_input = input()
                    self.handle_user_input(user_input)
                    self.print_status()
                    self.last_status_print = time.time()
                else:
                    time.sleep(0.1)
            except ImportError:
                import select
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    user_input = input()
                    self.handle_user_input(user_input)
                    self.print_status()
                    self.last_status_print = time.time()
                else:
                    time.sleep(0.1)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Automation Server')
    parser.add_argument('--repo-url', type=str, help='Remote Git repository URL')
    parser.add_argument('--interval', type=int, default=5, help='File check interval (sec)')
    
    args = parser.parse_args()
    
    server = AutomationServer(repo_url=args.repo_url)
    server.run(check_interval=args.interval)


if __name__ == "__main__":
    main()