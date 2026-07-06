# server-control
Repo for controlling my home server

# Установка зависимостей
pip install -r requirements.txt

# Базовый запуск с локальным репозиторием
python main.py

# Запуск с удаленным репозиторием
python main.py --repo-url https://github.com/user/repo.git

# Настройка интервала проверки
python main.py --interval 10