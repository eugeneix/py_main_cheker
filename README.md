# Веб-монитор с уведомлениями в Telegram

Python-приложение для мониторинга изменений текста элемента на веб-странице с отправкой уведомлений в Telegram.

## Возможности

- ✅ Автоматическая проверка веб-страницы каждые 60 секунд
- ✅ Определение изменений текста элемента
- ✅ Уведомления в Telegram при обнаружении изменений
- ✅ Автоматический перезапуск при ошибках
- ✅ Подробное логирование
- ✅ Поддержка различных типов селекторов (CSS, XPath, ID)
- ✅ Работа в headless режиме (без графического интерфейса)

## Требования

- Ubuntu/Debian Linux
- Python 3.10 или выше
- Google Chrome
- ChromeDriver

## Установка

### 1. Установка системных зависимостей

```bash
# Обновляем список пакетов
sudo apt update

# Устанавливаем Python и pip
sudo apt install -y python3 python3-pip

# Устанавливаем Google Chrome
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
sudo apt update
sudo apt install -y google-chrome-stable

# Устанавливаем ChromeDriver (автоматически через Selenium Manager)
# Или вручную:
# wget https://chromedriver.storage.googleapis.com/LATEST_RELEASE
# VERSION=$(cat LATEST_RELEASE)
# wget https://chromedriver.storage.googleapis.com/$VERSION/chromedriver_linux64.zip
# unzip chromedriver_linux64.zip
# sudo mv chromedriver /usr/local/bin/
# sudo chmod +x /usr/local/bin/chromedriver
```

### 2. Установка Python-зависимостей

```bash
# Переходим в директорию проекта
cd /path/to/py_main_cheker

# Устанавливаем зависимости
pip3 install -r requirements.txt
```

### 3. Создание Telegram бота

1. Откройте Telegram и найдите бота [@BotFather](https://t.me/BotFather)
2. Отправьте команду `/newbot`
3. Следуйте инструкциям и придумайте имя и username для бота
4. BotFather выдаст вам токен вида: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
5. Сохраните этот токен

### 4. Получение Chat ID

**Способ 1: Через бота @userinfobot**
1. Найдите бота [@userinfobot](https://t.me/userinfobot) в Telegram
2. Отправьте ему любое сообщение
3. Бот вернет ваш Chat ID

**Способ 2: Через API**
1. Отправьте сообщение вашему боту (любое)
2. Откройте в браузере:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
   Замените `<YOUR_TOKEN>` на токен вашего бота
3. Найдите в ответе `"chat":{"id":123456789}` - это и есть ваш Chat ID

**Способ 3: Через группу или канал**
Если хотите отправлять в группу или канал:
1. Добавьте бота в группу/канал
2. Сделайте бота администратором (для каналов обязательно)
3. Получите Chat ID:
   - Добавьте [@userinfobot](https://t.me/userinfobot) в группу/канал
   - Отправьте `/start` в группе/канале
   - Бот вернет Chat ID (отрицательное число, например: `-1001234567890`)
4. Используйте этот Chat ID при запуске (см. подробную инструкцию в `TELEGRAM_GROUP_CHANNEL.md`)

## Использование

### Способ 1: Проверка наличия конкретного текста (рекомендуется)

Для проверки наличия элемента с конкретным текстом (например, "Рождество 2026"):

```bash
python3 web_monitor.py \
  "https://www.rtoperator.ru/" \
  "ВАШ_ТОКЕН" \
  "ВАШ_CHAT_ID" \
  "auto" \
  "Рождество 2026"
```

Или через переменные окружения:

```bash
export MONITOR_URL="https://www.rtoperator.ru/"
export MONITOR_SELECTOR="auto"
export MONITOR_EXPECTED_TEXT="Рождество 2026"
export TELEGRAM_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
export TELEGRAM_CHAT_ID="123456789"

python3 web_monitor.py
```

### Способ 2: Проверка изменения элемента по селектору

```bash
python3 web_monitor.py \
  "https://example.com/page" \
  "ВАШ_ТОКЕН" \
  "ВАШ_CHAT_ID" \
  "#status"
```

### Способ 3: Проверка конкретного текста в элементе по селектору

```bash
python3 web_monitor.py \
  "https://example.com/page" \
  "ВАШ_ТОКЕН" \
  "ВАШ_CHAT_ID" \
  "//div[@class='tour-category']" \
  "Рождество 2026"
```

### Примеры использования

**Проверка наличия текста "Рождество 2026" на сайте rtoperator.ru:**
```bash
python3 web_monitor.py \
  "https://www.rtoperator.ru/" \
  "TOKEN" \
  "CHAT_ID" \
  "auto" \
  "Рождество 2026"
```

**Проверка изменения элемента по CSS селектору:**
```bash
python3 web_monitor.py "https://example.com" "TOKEN" "CHAT_ID" "#status"
```

**Проверка конкретного текста в элементе по XPath:**
```bash
python3 web_monitor.py \
  "https://example.com" \
  "TOKEN" \
  "CHAT_ID" \
  "//div[@class='tour-category']" \
  "Рождество 2026"
```

### Как работает проверка наличия текста

Если указан параметр `EXPECTED_TEXT`:
- ✅ Приложение ищет элемент, содержащий указанный текст
- ✅ Если текст найден и соответствует ожидаемому - всё в порядке
- ⚠️ Если текст изменился (например, "Рождество 2026" → "Ноябрьские праздники") - отправляется уведомление
- ⚠️ Если элемент не найден - отправляется уведомление
- ✅ Если элемент снова появился - отправляется уведомление о восстановлении

## Автозапуск через systemd

Для автоматического запуска приложения при загрузке VPS создайте systemd сервис.

### 1. Создание сервиса

Создайте файл `/etc/systemd/system/web-monitor.service`:

```bash
sudo nano /etc/systemd/system/web-monitor.service
```

Вставьте следующее содержимое (замените пути и параметры на свои):

```ini
[Unit]
Description=Web Monitor with Telegram Notifications
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/py_main_cheker
Environment="MONITOR_URL=https://example.com/page"
Environment="MONITOR_SELECTOR=#status"
Environment="TELEGRAM_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
Environment="TELEGRAM_CHAT_ID=123456789"
ExecStart=/usr/bin/python3 /path/to/py_main_cheker/web_monitor.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Важно:** Замените:
- `your_username` - на ваше имя пользователя
- `/path/to/py_main_cheker` - на полный путь к директории проекта
- Значения переменных окружения на ваши

### 2. Активация сервиса

```bash
# Перезагружаем конфигурацию systemd
sudo systemctl daemon-reload

# Включаем автозапуск
sudo systemctl enable web-monitor.service

# Запускаем сервис
sudo systemctl start web-monitor.service

# Проверяем статус
sudo systemctl status web-monitor.service
```

### 3. Управление сервисом

```bash
# Остановить
sudo systemctl stop web-monitor.service

# Запустить
sudo systemctl start web-monitor.service

# Перезапустить
sudo systemctl restart web-monitor.service

# Посмотреть логи
sudo journalctl -u web-monitor.service -f
```

## Логирование

Приложение создает файл `web_monitor.log` в директории проекта с подробными логами всех операций.

Для просмотра логов в реальном времени:
```bash
tail -f web_monitor.log
```

## Обработка ошибок

Приложение автоматически обрабатывает следующие ситуации:

- Элемент временно недоступен - пропускает проверку и продолжает мониторинг
- Ошибка WebDriver - перезапускает драйвер
- Ошибка Telegram API - логирует ошибку и продолжает работу
- Слишком много ошибок подряд - перезапускает WebDriver

## Структура проекта

```
py_main_cheker/
├── web_monitor.py          # Основной скрипт
├── requirements.txt        # Python зависимости
├── config.example.py       # Пример конфигурации
├── README.md              # Документация
└── web_monitor.log        # Файл логов (создается автоматически)
```

## Устранение неполадок

### ChromeDriver не найден

Selenium 4.6+ автоматически управляет ChromeDriver через Selenium Manager. Если возникают проблемы:

```bash
# Проверьте версию Chrome
google-chrome --version

# Установите ChromeDriver вручную (см. раздел установки)
```

### Ошибка "Element not found"

- Проверьте правильность селектора
- Убедитесь, что элемент существует на странице
- Попробуйте использовать XPath вместо CSS селектора

### Ошибка Telegram API

- Проверьте правильность токена
- Убедитесь, что бот запущен (отправьте ему `/start`)
- Проверьте правильность Chat ID

### Проблемы с правами доступа

Если используете systemd, убедитесь что:
- Пользователь имеет права на чтение/запись в директории проекта
- Chrome может запускаться от имени пользователя

## Безопасность

⚠️ **Важно:** Не публикуйте токен Telegram бота и Chat ID в публичных репозиториях!

Для production используйте:
- Переменные окружения
- Файлы конфигурации с ограниченными правами доступа (chmod 600)
- Secrets management системы

## Лицензия

Этот проект предоставляется "как есть" для личного использования.
