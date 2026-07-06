
---
"""
        
        try:
            # Читаем существующий файл
            if RESULTS_FILE.exists():
                old_content = RESULTS_FILE.read_text(encoding='utf-8')
                
                # Находим позицию после заголовка
                header_end = old_content.find("---\n\n")
                if header_end != -1:
                    header_end += 5
                    # Вставляем новую запись после заголовка
                    new_content = old_content[:header_end] + entry + old_content[header_end:]
                else:
                    new_content = entry + old_content
            else:
                new_content = f"""# 📊 Результаты выполнения команд

**Сервер запущен:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
{entry}"""
            
            RESULTS_FILE.write_text(new_content, encoding='utf-8')
            
        except Exception as e:
            print(f"⚠ Ошибка записи в RESULTS.md: {e}")
    
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

📋 commands.txt | 🖱 inputs.txt | 📊 RESULTS.md | 📸 screenshots/
⏎  Введите команду или 'help':""", end=' ', flush=True)
    
    def pull_changes(self):
        """Получение изменений из Git."""
        if self.repo_url:
            try:
                origin = self.repo.remotes.origin
                origin.pull()
            except Exception as e:
                pass
    
    def push_changes(self, message: str = "Automated commit"):
        """Отправка изменений в Git."""
        try:
            # Добавляем важные файлы
            self.repo.index.add([
                'RESULTS.md',
                'commands.txt', 
                'inputs.txt',
                'screenshots/*.png'
            ])
            
            if self.repo.is_dirty() or self.repo.untracked_files:
                self.repo.index.commit(message)
                if self.repo_url:
                    self.repo.remotes.origin.push()
        except Exception as e:
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
            
            print(f"\n📸 Создание скриншота...")
            
            with mss() as sct:
                sct.shot(output=str(screenshot_path))
            
            img = Image.open(screenshot_path)
            img.save(screenshot_path, optimize=True, quality=85)
            
            size_mb = screenshot_path.stat().st_size / (1024 * 1024)
            self.screenshots_taken += 1
            
            # Очистка старых скриншотов
            self.cleanup_old_screenshots()
            
            success_msg = f"Скриншот создан: {filename} ({size_mb:.2f} MB)"
            print(f"✅ {success_msg}")
            
            self.last_activity = f"Скриншот: {filename}"
            
            # Добавляем в RESULTS.md
            self.add_to_results("screenshot", "get_screenshot", 
                              f"Скриншот сохранен: {filename}\nРазмер: {size_mb:.2f} MB\nПуть: screenshots/{filename}", 
                              True)
            
            return True, success_msg
            
        except Exception as e:
            self.errors_count += 1
            error_msg = f"Ошибка скриншота: {str(e)}"
            print(f"❌ {error_msg}")
            
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
            
            print(f"\n▶ Выполнение: {command}")
            
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
            
            # Выводим результат в консоль
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(f"⚠ {result.stderr}")
            
            success = result.returncode == 0
            
            self.commands_executed += 1
            self.last_activity = f"Команда: {command[:50]}"
            
            if success:
                print(f"✅ Выполнено успешно")
            else:
                self.errors_count += 1
                print(f"❌ Ошибка (код {result.returncode})")
            
            # Добавляем в RESULTS.md
            self.add_to_results("command", command, output, success)
            
            return success, output
            
        except subprocess.TimeoutExpired:
            self.errors_count += 1
            error_msg = "⏱ Превышен лимит времени (300с)"
            print(f"❌ {error_msg}")
            self.add_to_results("command", command, error_msg, False)
            return False, error_msg
        except Exception as e:
            self.errors_count += 1
            error_msg = f"Ошибка: {str(e)}"
            print(f"❌ {error_msg}")
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
                print(f"⏱ Задержка {duration}с...")
                time.sleep(duration)
                msg = f"Задержка {duration}с"
                self.add_to_results("input", "delay", msg, True)
                return True, msg
            
            elif input_type == 'click':
                screen_width, screen_height = pyautogui.size()
                x = int(input_data['x'] * screen_width)
                y = int(input_data['y'] * screen_height)
                button = input_data.get('button', 'left')
                
                print(f"🖱 Клик ({x}, {y}) - {button}")
                pyautogui.click(x, y, button=button)
                msg = f"Клик ({x}, {y}) - {button}"
                self.add_to_results("input", f"click [{input_data['x']}, {input_data['y']}]", msg, True)
                return True, msg
            
            elif input_type == 'keyboard':
                keys = input_data.get('keys', '')
                print(f"⌨ Ввод: {keys}")
                
                if '+' in keys:
                    pyautogui.hotkey(*keys.split('+'))
                else:
                    pyautogui.typewrite(keys)
                
                msg = f"Клавиши: {keys}"
                self.add_to_results("input", "keyboard", msg, True)
                return True, msg
            
            return False, f"Неизвестный тип: {input_type}"
            
        except Exception as e:
            error_msg = f"Ошибка ввода: {str(e)}"
            self.add_to_results("input", str(input_data), error_msg, False)
            return False, error_msg
    
    def process_inputs(self):
        """Обработка команд ввода."""
        try:
            inputs = self.read_inputs()
            if not inputs:
                return
            
            print(f"\n⌨ Выполнение {len(inputs)} команд ввода:")
            
            results_summary = []
            for i, input_data in enumerate(inputs, 1):
                success, message = self.execute_input(input_data)
                status = "✅" if success else "❌"
                print(f"  {i}. {status} {message}")
                results_summary.append(f"{i}. {status} {message}")
                if not success:
                    self.errors_count += 1
            
            self.inputs_processed += len(inputs)
            self.last_activity = f"Обработано {len(inputs)} вводов"
            
            # Добавляем сводку ввода в RESULTS.md
            summary = "\n".join(results_summary)
            self.add_to_results("input", f"Пакет из {len(inputs)} команд", summary, True)
            
            # Очищаем файл после выполнения
            INPUTS_FILE.write_text(
                "# Команды ввода\n# Формат:\n# type: click\n# coordinates: [0.5, 0.5]\n# button: left\n\n",
                encoding='utf-8'
            )
            
        except Exception as e:
            self.errors_count += 1
            print(f"❌ Ошибка обработки ввода: {e}")
    
    def show_help(self):
        """Показ справки."""
        print("""
╔══════════════════════════════════════════════════════════════╗
║                    ДОСТУПНЫЕ КОМАНДЫ                         ║
╠══════════════════════════════════════════════════════════════╣
║ screen, scr     - Создать скриншот                          ║
║ status, st      - Показать статус                           ║
║ exec, run [cmd] - Выполнить команду в консоли               ║
║   Пример: exec dir                                         ║
║   Пример: exec echo Привет                                 ║
║ click [x] [y]   - Клик мышью (координаты 0.0-1.0)          ║
║   Пример: click 0.5 0.5  (центр экрана)                    ║
║   Пример: click 0.1 0.1  (левый верхний угол)              ║
║ type [текст]    - Напечатать текст                          ║
║   Пример: type Привет, мир!                                ║
║ hotkey [клавиши] - Нажать комбинацию клавиш                ║
║   Пример: hotkey ctrl+c                                    ║
║   Пример: hotkey alt+tab                                   ║
║ results         - Показать RESULTS.md                       ║
║ help, ?         - Показать эту справку                      ║
║ quit, exit      - Выход                                    ║
║                                                             ║
║ Сервер проверяет commands.txt и inputs.txt                 ║
║ Все результаты сохраняются в RESULTS.md                    ║
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
                print("❌ Укажите команду. Пример: exec dir")
        elif cmd == 'click':
            try:
                coords = args.split()
                if len(coords) == 2:
                    x, y = float(coords[0]), float(coords[1])
                    screen_w, screen_h = pyautogui.size()
                    click_x = int(x * screen_w)
                    click_y = int(y * screen_h)
                    print(f"🖱 Клик ({click_x}, {click_y})")
                    pyautogui.click(click_x, click_y)
                    self.inputs_processed += 1
                    self.last_activity = f"Клик ({click_x}, {click_y})"
                    self.add_to_results("input", f"click {x} {y}", 
                                      f"Клик ({click_x}, {click_y})", True)
                else:
                    print("❌ Формат: click X Y (например: click 0.5 0.5)")
            except ValueError:
                print("❌ Координаты должны быть числами")
        elif cmd == 'type':
            if args:
                print(f"⌨ Печать: {args}")
                pyautogui.typewrite(args)
                self.inputs_processed += 1
                self.last_activity = f"Ввод текста"
                self.add_to_results("input", "type", f"Текст: {args}", True)
            else:
                print("❌ Укажите текст. Пример: type Привет")
        elif cmd == 'hotkey':
            if args:
                keys = args.replace(' ', '').split('+')
                print(f"⌨ Комбинация: {'+'.join(keys)}")
                pyautogui.hotkey(*keys)
                self.inputs_processed += 1
                self.last_activity = f"Hotkey: {'+'.join(keys)}"
                self.add_to_results("input", "hotkey", f"Комбинация: {'+'.join(keys)}", True)
            else:
                print("❌ Укажите клавиши. Пример: hotkey ctrl+c")
        elif cmd == 'results':
            if RESULTS_FILE.exists():
                print("\n" + "="*60)
                print("Содержимое RESULTS.md:")
                print("="*60)
                print(RESULTS_FILE.read_text(encoding='utf-8'))
            else:
                print("❌ Файл RESULTS.md еще не создан")
        elif cmd in ['help', '?']:
            self.show_help()
        elif cmd in ['quit', 'exit']:
            self.current_status = "STOPPING"
            print("\n⚠ Завершение работы...")
            self.add_to_results("system", "shutdown", "Сервер остановлен пользователем", True)
            self.push_changes("Server stopped")
            sys.exit(0)
        elif cmd:
            # Выполняем как консольную команду
            self.execute_command(user_input)
            self.commands_executed += 1
        
        if cmd not in ['status', 'st', 'quit', 'exit']:
            input("\nНажмите Enter для продолжения...")
    
    def run(self, check_interval: int = 5):
        """Главный цикл сервера."""
        self.print_status()
        
        # Поток для проверки файлов
        def file_checker():
            while self.current_status == "RUNNING":
                with command_lock:
                    self.pull_changes()
                    
                    # Проверка commands.txt
                    commands = self.read_commands()
                    executed = self.get_executed_commands()
                    
                    new_commands = []
                    for cmd in commands:
                        cmd_hash = hashlib.md5(cmd.encode('utf-8')).hexdigest()
                        if cmd_hash not in executed:
                            new_commands.append(cmd)
                    
                    if new_commands:
                        print(f"\n📋 Найдено {len(new_commands)} новых команд в файле")
                        for cmd in new_commands:
                            self.execute_command(cmd)
                            self.mark_command_executed(cmd)
                        self.push_changes(f"Executed {len(new_commands)} commands")
                        print("\nНажмите Enter для продолжения...")
                    
                    # Проверка inputs.txt
                    if INPUTS_FILE.exists():
                        content = self.safe_read_file(INPUTS_FILE)
                        has_commands = any(
                            line.strip() and not line.strip().startswith('#') 
                            for line in content.splitlines()
                        )
                        if has_commands:
                            print("\n📋 Обнаружены команды ввода в файле")
                            self.process_inputs()
                            self.push_changes("Processed inputs")
                            print("\nНажмите Enter для продолжения...")
                
                time.sleep(check_interval)
        
        checker_thread = threading.Thread(target=file_checker, daemon=True)
        checker_thread.start()
        
        # Главный цикл
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
    
    parser = argparse.ArgumentParser(description='Автономный сервер автоматизации')
    parser.add_argument('--repo-url', type=str, help='URL удаленного Git репозитория')
    parser.add_argument('--interval', type=int, default=5, help='Интервал проверки файлов (сек)')
    
    args = parser.parse_args()
    
    server = AutomationServer(repo_url=args.repo_url)
    server.run(check_interval=args.interval)


if __name__ == "__main__":
    main()