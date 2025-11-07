# Пример конфигурационного файла
# Скопируйте этот файл в config.py и заполните своими данными

# URL страницы для мониторинга
MONITOR_URL = "https://example.com/page"

# Селектор элемента (CSS селектор, XPath или ID)
# Примеры:
#   CSS: "#status" или ".status-text" или "div.status"
#   XPath: "//div[@id='status']" или "//span[contains(@class, 'status')]"
#   ID: "#status" (без # будет использован как CSS селектор)
MONITOR_SELECTOR = "#status"

# Токен Telegram бота (получить у @BotFather)
TELEGRAM_TOKEN = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"

# ID чата для отправки уведомлений
# Как получить: отправьте боту сообщение, затем откройте:
# https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
# Найдите "chat":{"id":123456789} в ответе
TELEGRAM_CHAT_ID = "123456789"

