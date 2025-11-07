#!/bin/bash
# Скрипт установки веб-монитора на Ubuntu/Debian VPS

set -e

echo "=========================================="
echo "Установка веб-монитора"
echo "=========================================="

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo "Пожалуйста, запустите скрипт с sudo"
    exit 1
fi

# Обновление списка пакетов
echo "Обновление списка пакетов..."
apt update

# Установка Python и pip
echo "Установка Python и pip..."
apt install -y python3 python3-pip

# Установка Google Chrome
echo "Установка Google Chrome..."
if ! command -v google-chrome &> /dev/null; then
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -
    sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
    apt update
    apt install -y google-chrome-stable
    echo "Google Chrome установлен"
else
    echo "Google Chrome уже установлен"
fi

# Установка Python зависимостей
echo "Установка Python зависимостей..."
pip3 install -r requirements.txt

echo ""
echo "=========================================="
echo "Установка завершена!"
echo "=========================================="
echo ""
echo "Следующие шаги:"
echo "1. Создайте Telegram бота через @BotFather"
echo "2. Получите Chat ID (см. README.md)"
echo "3. Запустите приложение:"
echo "   python3 web_monitor.py <URL> <SELECTOR> <TOKEN> <CHAT_ID>"
echo ""
echo "Или используйте переменные окружения (см. README.md)"

