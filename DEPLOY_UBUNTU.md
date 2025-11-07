# Развертывание на Ubuntu сервере

## Быстрая инструкция

### 1. Клонирование проекта на сервер

```bash
# Подключитесь к серверу
ssh ваш_пользователь@ваш_сервер_ip

# Клонируйте репозиторий
git clone https://github.com/eugeneix/py_main_cheker.git
cd py_main_cheker
```

### 2. Установка зависимостей

```bash
# Запустите скрипт установки
sudo bash install.sh

# Или установите вручную:
sudo apt update
sudo apt install -y python3 python3-pip google-chrome-stable
pip3 install -r requirements.txt
```

### 3. Настройка и запуск

```bash
# Запустите с вашими параметрами
python3 web_monitor.py \
  "https://www.rtoperator.ru/" \
  "8208055846:AAFNFYKN4mPfvO4aPQ13xOr4aqGw_ayuyCA" \
  "@lelelelasd" \
  "auto" \
  "Рождество 2026"
```

### 4. Настройка автозапуска (systemd)

```bash
# Отредактируйте сервис
sudo nano /etc/systemd/system/web-monitor.service
```

Вставьте (замените пути и параметры):

```ini
[Unit]
Description=Web Monitor - Рождество 2026 на rtoperator.ru
After=network.target

[Service]
Type=simple
User=ваш_пользователь
WorkingDirectory=/home/ваш_пользователь/py_main_cheker
Environment="MONITOR_URL=https://www.rtoperator.ru/"
Environment="MONITOR_SELECTOR=auto"
Environment="MONITOR_EXPECTED_TEXT=Рождество 2026"
Environment="TELEGRAM_TOKEN=8208055846:AAFNFYKN4mPfvO4aPQ13xOr4aqGw_ayuyCA"
Environment="TELEGRAM_CHAT_ID=@lelelelasd"
ExecStart=/usr/bin/python3 /home/ваш_пользователь/py_main_cheker/web_monitor.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Активируйте:

```bash
sudo systemctl daemon-reload
sudo systemctl enable web-monitor.service
sudo systemctl start web-monitor.service
sudo systemctl status web-monitor.service
```

### 5. Просмотр логов

```bash
# Логи systemd
sudo journalctl -u web-monitor.service -f

# Или файл логов
tail -f web_monitor.log
```

## Готово!

Приложение будет:
- ✅ Автоматически запускаться при перезагрузке сервера
- ✅ Проверять страницу каждую минуту с полной очисткой кэша
- ✅ Отправлять уведомления в Telegram канал @lelelelasd
- ✅ Автоматически перезапускаться при ошибках

