#!/bin/bash
# Скрипт для запуска мониторинга rtoperator.ru

# Замените значения на свои
URL="https://www.rtoperator.ru/"
SELECTOR="auto"
EXPECTED_TEXT="Рождество 2026"
TELEGRAM_TOKEN="ВАШ_ТОКЕН"
TELEGRAM_CHAT_ID="ВАШ_CHAT_ID"

# Запуск монитора
python3 web_monitor.py "$URL" "$TELEGRAM_TOKEN" "$TELEGRAM_CHAT_ID" "$SELECTOR" "$EXPECTED_TEXT"

