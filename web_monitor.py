#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Веб-монитор с уведомлениями в Telegram
Проверяет изменения текста элемента на веб-странице каждые 60 секунд
"""

import time
import logging
import sys
from datetime import datetime
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException
)

try:
    # Для python-telegram-bot >= 20.0
    from telegram import Bot
    from telegram.error import TelegramError
except ImportError:
    # Для старых версий
    import telegram
    from telegram.error import TelegramError
    Bot = telegram.Bot

try:
    # Python 3.9+
    from zoneinfo import ZoneInfo
    MOSCOW_TZ = ZoneInfo('Europe/Moscow')
except ImportError:
    # Python < 3.9
    try:
        import pytz
        MOSCOW_TZ = pytz.timezone('Europe/Moscow')
    except ImportError:
        # Если pytz не установлен, используем UTC (не рекомендуется)
        MOSCOW_TZ = None

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('web_monitor.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class WebMonitor:
    """Класс для мониторинга веб-страницы и отправки уведомлений в Telegram"""
    
    def __init__(self, url: str, selector: str, telegram_token: str, chat_id: str, expected_text: Optional[str] = None):
        """
        Инициализация монитора
        
        Args:
            url: URL страницы для мониторинга
            selector: CSS селектор, XPath или ID элемента
            telegram_token: Токен Telegram бота
            chat_id: ID чата для отправки уведомлений
            expected_text: Ожидаемый текст элемента (если задан, проверяется наличие этого текста)
        """
        self.url = url
        self.selector = selector
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.expected_text = expected_text
        self.previous_text: Optional[str] = None
        self.driver: Optional[webdriver.Chrome] = None
        self.bot = Bot(token=telegram_token)
        self.element_found_last_time = True  # Флаг для отслеживания, был ли элемент найден в прошлый раз
        
    def _setup_driver(self) -> webdriver.Chrome:
        """Настройка и создание Chrome WebDriver"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Без графического интерфейса
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36')
        
        # Отключаем логирование Chrome
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            # Пытаемся найти chromedriver в системе
            service = Service()
            driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("ChromeDriver успешно инициализирован")
            return driver
        except Exception as e:
            logger.error(f"Ошибка при создании WebDriver: {e}")
            raise
    
    def _get_element_text(self) -> Optional[str]:
        """
        Получение текста элемента со страницы
        
        Returns:
            Текст элемента или None в случае ошибки
        """
        try:
            # Определяем тип селектора
            if self.selector.startswith('//') or self.selector.startswith('(//'):
                # XPath
                element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, self.selector))
                )
            elif self.selector.startswith('#'):
                # ID селектор
                element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, self.selector[1:]))
                )
            elif self.selector.startswith('.'):
                # CSS класс
                element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, self.selector))
                )
            else:
                # CSS селектор или другой
                element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, self.selector))
                )
            
            text = element.text.strip()
            logger.debug(f"Получен текст элемента: {text[:50]}...")
            return text
            
        except TimeoutException:
            logger.warning(f"Элемент с селектором '{self.selector}' не найден на странице (таймаут)")
            return None
        except NoSuchElementException:
            logger.warning(f"Элемент с селектором '{self.selector}' не найден на странице")
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении текста элемента: {e}")
            return None
    
    def _find_element_by_text(self, text: str) -> Optional[str]:
        """
        Поиск элемента по тексту (используется, если селектор не указан)
        
        Args:
            text: Текст для поиска
            
        Returns:
            Текст найденного элемента или None
        """
        try:
            # Ищем элемент, содержащий указанный текст
            xpath = f"//*[contains(text(), '{text}')]"
            element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            found_text = element.text.strip()
            logger.debug(f"Найден элемент с текстом: {found_text[:50]}...")
            return found_text
        except (TimeoutException, NoSuchElementException):
            logger.warning(f"Элемент с текстом '{text}' не найден на странице")
            return None
        except Exception as e:
            logger.error(f"Ошибка при поиске элемента по тексту: {e}")
            return None
    
    def _send_telegram_notification(self, message_type: str, current_text: Optional[str] = None):
        """
        Отправка уведомления в Telegram
        
        Args:
            message_type: Тип сообщения ('changed', 'missing', 'found_again')
            current_text: Текущий текст элемента (если есть)
        """
        try:
            # Получаем текущее время по Москве
            if MOSCOW_TZ:
                moscow_time = datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M')
            else:
                moscow_time = datetime.now().strftime('%Y-%m-%d %H:%M')
            
            if message_type == 'changed':
                message = (
                    f"⚠️ Элемент изменился!\n\n"
                    f"Время: {moscow_time} (МСК)\n"
                    f"Ожидался: {self.expected_text}\n"
                    f"Найден: {current_text[:200] if current_text else 'не найден'}"
                )
            elif message_type == 'missing':
                message = (
                    f"⚠️ Элемент отсутствует!\n\n"
                    f"Время: {moscow_time} (МСК)\n"
                    f"Ожидался элемент с текстом: {self.expected_text}\n"
                    f"Элемент не найден на странице"
                )
            elif message_type == 'found_again':
                message = (
                    f"✅ Элемент снова найден!\n\n"
                    f"Время: {moscow_time} (МСК)\n"
                    f"Текст: {current_text[:200] if current_text else 'найден'}"
                )
            else:
                # Стандартное уведомление об изменении
                message = (
                    f"⚠️ Элемент изменился\n\n"
                    f"Время: {moscow_time} (МСК)\n"
                    f"Новый текст: {current_text[:200] if current_text else 'не найден'}"
                )
            
            self.bot.send_message(chat_id=self.chat_id, text=message)
            logger.info("Уведомление успешно отправлено в Telegram")
            
        except TelegramError as e:
            logger.error(f"Ошибка при отправке сообщения в Telegram: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке в Telegram: {e}")
    
    def _check_page(self) -> bool:
        """
        Проверка страницы на изменения
        
        Returns:
            True если проверка прошла успешно, False в случае ошибки
        """
        try:
            # Открываем или обновляем страницу
            logger.debug(f"Открываем страницу: {self.url}")
            self.driver.get(self.url)
            
            # Ждем загрузки страницы
            time.sleep(3)  # Увеличиваем время для динамических страниц
            
            # Если задан ожидаемый текст, используем специальную логику проверки
            if self.expected_text:
                return self._check_expected_text()
            
            # Стандартная логика: проверка изменения текста
            current_text = self._get_element_text()
            
            if current_text is None:
                logger.warning("Не удалось получить текст элемента, пропускаем проверку")
                return False
            
            # Сравниваем с предыдущим значением
            if self.previous_text is None:
                logger.info(f"Первая проверка. Текущий текст: {current_text[:50]}...")
                self.previous_text = current_text
                return True
            
            if current_text != self.previous_text:
                logger.info("Обнаружено изменение текста элемента!")
                logger.info(f"Было: {self.previous_text[:50]}...")
                logger.info(f"Стало: {current_text[:50]}...")
                
                # Отправляем уведомление
                self._send_telegram_notification('changed', current_text)
                
                # Обновляем предыдущее значение
                self.previous_text = current_text
            else:
                logger.debug("Текст элемента не изменился")
            
            return True
            
        except WebDriverException as e:
            logger.error(f"Ошибка WebDriver: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при проверке страницы: {e}")
            return False
    
    def _check_expected_text(self) -> bool:
        """
        Проверка наличия элемента с ожидаемым текстом
        
        Returns:
            True если проверка прошла успешно, False в случае ошибки
        """
        current_text = None
        
        # Если селектор указан, используем его
        if self.selector and self.selector != 'auto':
            current_text = self._get_element_text()
        else:
            # Иначе ищем элемент по тексту
            current_text = self._find_element_by_text(self.expected_text)
        
        # Проверяем, найден ли элемент и соответствует ли текст ожидаемому
        if current_text is None:
            # Элемент не найден
            if self.element_found_last_time:
                # Элемент пропал - отправляем уведомление
                logger.warning(f"⚠️ Элемент '{self.expected_text}' не найден на странице!")
                self._send_telegram_notification('missing')
                self.element_found_last_time = False
            else:
                logger.debug(f"Элемент '{self.expected_text}' по-прежнему отсутствует")
            return True
        
        # Элемент найден, проверяем текст
        if self.expected_text.lower() in current_text.lower():
            # Текст соответствует ожидаемому
            if not self.element_found_last_time:
                # Элемент снова появился - отправляем уведомление
                logger.info(f"✅ Элемент '{self.expected_text}' снова найден!")
                self._send_telegram_notification('found_again', current_text)
            else:
                logger.debug(f"✅ Элемент '{self.expected_text}' присутствует на странице")
            self.element_found_last_time = True
        else:
            # Текст не соответствует ожидаемому
            logger.warning(f"⚠️ Элемент найден, но текст изменился!")
            logger.warning(f"Ожидался: '{self.expected_text}'")
            logger.warning(f"Найден: '{current_text}'")
            self._send_telegram_notification('changed', current_text)
            self.element_found_last_time = False
        
        return True
    
    def _restart_driver(self):
        """Перезапуск WebDriver"""
        try:
            if self.driver:
                self.driver.quit()
        except Exception as e:
            logger.warning(f"Ошибка при закрытии драйвера: {e}")
        
        try:
            self.driver = self._setup_driver()
        except Exception as e:
            logger.error(f"Не удалось перезапустить драйвер: {e}")
            raise
    
    def _test_telegram_connection(self) -> bool:
        """Проверка подключения к Telegram"""
        try:
            # Пытаемся получить информацию о боте
            bot_info = self.bot.get_me()
            logger.info(f"Telegram бот подключен: @{bot_info.username}")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к Telegram: {e}")
            logger.error("Проверьте правильность токена")
            return False
    
    def run(self):
        """Основной цикл мониторинга"""
        logger.info("=" * 60)
        logger.info("Запуск веб-монитора")
        logger.info(f"URL: {self.url}")
        logger.info(f"Селектор: {self.selector}")
        if self.expected_text:
            logger.info(f"Ожидаемый текст: {self.expected_text}")
        logger.info("=" * 60)
        
        # Проверка подключения к Telegram
        if not self._test_telegram_connection():
            logger.error("Не удалось подключиться к Telegram. Проверьте токен и интернет-соединение.")
            sys.exit(1)
        
        # Инициализация драйвера
        try:
            self.driver = self._setup_driver()
        except Exception as e:
            logger.error(f"Критическая ошибка: не удалось создать WebDriver. {e}")
            logger.error("Убедитесь, что Chrome и ChromeDriver установлены")
            sys.exit(1)
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while True:
            try:
                success = self._check_page()
                
                if success:
                    consecutive_errors = 0
                    logger.info(f"Проверка завершена. Следующая проверка через 60 секунд...")
                else:
                    consecutive_errors += 1
                    logger.warning(f"Ошибка при проверке (попытка {consecutive_errors}/{max_consecutive_errors})")
                    
                    # Если слишком много ошибок подряд - перезапускаем драйвер
                    if consecutive_errors >= max_consecutive_errors:
                        logger.warning("Слишком много ошибок подряд. Перезапускаем WebDriver...")
                        self._restart_driver()
                        consecutive_errors = 0
                
                # Ждем 60 секунд до следующей проверки
                time.sleep(60)
                
            except KeyboardInterrupt:
                logger.info("Получен сигнал остановки. Завершение работы...")
                break
            except Exception as e:
                logger.error(f"Критическая ошибка в основном цикле: {e}")
                consecutive_errors += 1
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Критическая ошибка. Перезапускаем WebDriver...")
                    try:
                        self._restart_driver()
                        consecutive_errors = 0
                    except Exception as e2:
                        logger.error(f"Не удалось перезапустить драйвер: {e2}")
                        logger.error("Ожидание 60 секунд перед следующей попыткой...")
                        time.sleep(60)
        
        # Закрываем драйвер при выходе
        try:
            if self.driver:
                self.driver.quit()
                logger.info("WebDriver закрыт")
        except Exception as e:
            logger.warning(f"Ошибка при закрытии драйвера: {e}")


def main():
    """Точка входа в программу"""
    import os
    
    # Получаем параметры из переменных окружения или аргументов командной строки
    url = os.getenv('MONITOR_URL')
    selector = os.getenv('MONITOR_SELECTOR', 'auto')  # По умолчанию 'auto' для поиска по тексту
    telegram_token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    expected_text = os.getenv('MONITOR_EXPECTED_TEXT')
    
    # Если параметры не заданы через переменные окружения, используем аргументы
    if not all([url, telegram_token, chat_id]):
        if len(sys.argv) < 4:
            print("Использование:")
            print("  python web_monitor.py <URL> <TELEGRAM_TOKEN> <CHAT_ID> [SELECTOR] [EXPECTED_TEXT]")
            print("\nИли установите переменные окружения:")
            print("  MONITOR_URL, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID")
            print("  MONITOR_SELECTOR (опционально, по умолчанию 'auto')")
            print("  MONITOR_EXPECTED_TEXT (опционально, для проверки конкретного текста)")
            print("\nПримеры:")
            print('  # Проверка наличия текста "Рождество 2026" (автопоиск)')
            print('  python web_monitor.py "https://example.com" "TOKEN" "CHAT_ID" "auto" "Рождество 2026"')
            print('  # Проверка изменения элемента по селектору')
            print('  python web_monitor.py "https://example.com" "TOKEN" "CHAT_ID" "#status"')
            print('  # Проверка конкретного текста в элементе')
            print('  python web_monitor.py "https://example.com" "TOKEN" "CHAT_ID" "//div[@class=\'tour\']" "Рождество 2026"')
            sys.exit(1)
        
        url = sys.argv[1]
        telegram_token = sys.argv[2]
        chat_id = sys.argv[3]
        selector = sys.argv[4] if len(sys.argv) > 4 else 'auto'
        expected_text = sys.argv[5] if len(sys.argv) > 5 else None
    
    # Создаем и запускаем монитор
    monitor = WebMonitor(url, selector, telegram_token, chat_id, expected_text)
    
    try:
        monitor.run()
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

