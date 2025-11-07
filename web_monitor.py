#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Веб-монитор с уведомлениями в Telegram
Проверяет изменения текста элемента на веб-странице каждые 3 минуты
"""

import time
import logging
import sys
import os
import asyncio
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
    try:
        MOSCOW_TZ = ZoneInfo('Europe/Moscow')
    except Exception:
        # Если zoneinfo не может найти таймзону (например, нет tzdata на Windows)
        try:
            import pytz
            MOSCOW_TZ = pytz.timezone('Europe/Moscow')
        except ImportError:
            MOSCOW_TZ = None
except ImportError:
    # Python < 3.9
    try:
        import pytz
        MOSCOW_TZ = pytz.timezone('Europe/Moscow')
    except ImportError:
        # Если pytz не установлен, используем UTC (не рекомендуется)
        MOSCOW_TZ = None

# Настройка кодировки для Windows
import platform
if platform.system() == 'Windows':
    import io
    # Устанавливаем UTF-8 для stdout на Windows
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Настройка логирования
class SafeStreamHandler(logging.StreamHandler):
    """StreamHandler с безопасной обработкой Unicode для Windows"""
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # Убираем эмодзи для совместимости с Windows консолью
            msg = msg.replace('⚠️', '[WARNING]').replace('✅', '[OK]').replace('❌', '[ERROR]')
            stream.write(msg + self.terminator)
            self.flush()
        except UnicodeEncodeError:
            # Если не удалось закодировать, используем ASCII
            try:
                msg = self.format(record).encode('ascii', errors='replace').decode('ascii')
                stream.write(msg + self.terminator)
                self.flush()
            except Exception:
                self.handleError(record)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('web_monitor.log', encoding='utf-8'),
        SafeStreamHandler(sys.stdout)
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
        self.last_ok_notification_time = 0  # Время последнего "OK" уведомления
        self.ok_notification_interval = 180  # Интервал между "OK" уведомлениями (3 минуты)
        
    def _setup_driver(self) -> webdriver.Chrome:
        """Настройка и создание Chrome WebDriver"""
        chrome_options = Options()
        
        # Проверяем, нужно ли запускать в headless режиме
        # На Windows для теста можно отключить headless
        headless_mode = os.getenv('HEADLESS', 'true').lower() == 'true'
        if headless_mode:
            chrome_options.add_argument('--headless')  # Без графического интерфейса
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Отключаем кэш для получения свежих данных каждый раз
        chrome_options.add_argument('--disable-application-cache')
        chrome_options.add_argument('--disable-cache')
        chrome_options.add_argument('--aggressive-cache-discard')
        chrome_options.add_argument('--disable-background-networking')
        
        # Определяем user-agent в зависимости от ОС
        import platform
        if platform.system() == 'Windows':
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        else:
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36')
        
        # Отключаем логирование Chrome
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Отключаем кэш через preferences
        prefs = {
            "profile.default_content_setting_values": {
                "images": 2,  # Разрешаем изображения, но отключаем кэш
            },
            "profile.managed_default_content_settings": {
                "images": 2
            }
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        try:
            # Пытаемся найти chromedriver в системе
            service = Service()
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Устанавливаем таймауты для операций
            driver.set_page_load_timeout(30)  # 30 секунд на загрузку страницы
            driver.implicitly_wait(10)  # 10 секунд на поиск элементов
            
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
            # Определяем тип селектора (таймаут 5 секунд)
            if self.selector.startswith('//') or self.selector.startswith('(//'):
                # XPath
                element = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, self.selector))
                )
            elif self.selector.startswith('#'):
                # ID селектор
                element = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, self.selector[1:]))
                )
            elif self.selector.startswith('.'):
                # CSS класс
                element = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, self.selector))
                )
            else:
                # CSS селектор или другой
                element = WebDriverWait(self.driver, 5).until(
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
            # Ищем элемент, содержащий указанный текст (уменьшаем таймаут до 5 секунд)
            xpath = f"//*[contains(text(), '{text}')]"
            element = WebDriverWait(self.driver, 5).until(
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
            elif message_type == 'ok':
                message = (
                    f"✅ Элемент на месте!\n\n"
                    f"Время: {moscow_time} (МСК)\n"
                    f"Текст: {current_text[:200] if current_text else 'найден'}\n"
                    f"Всё в порядке."
                )
            else:
                # Стандартное уведомление об изменении
                message = (
                    f"⚠️ Элемент изменился\n\n"
                    f"Время: {moscow_time} (МСК)\n"
                    f"Новый текст: {current_text[:200] if current_text else 'не найден'}"
                )
            
            # В python-telegram-bot 20+ методы асинхронные
            # Создаем новый event loop для каждого вызова
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            async def send_async():
                # Поддерживаем как Chat ID (число), так и username канала (строка с @)
                chat_id = self.chat_id
                # Если это строка и начинается с @, используем как username
                if isinstance(chat_id, str) and chat_id.startswith('@'):
                    await self.bot.send_message(chat_id=chat_id, text=message)
                else:
                    # Иначе используем как Chat ID (число)
                    await self.bot.send_message(chat_id=int(chat_id), text=message)
            
            loop.run_until_complete(send_async())
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
            # Устанавливаем таймауты для операций
            self.driver.set_page_load_timeout(30)  # 30 секунд на загрузку страницы
            self.driver.implicitly_wait(5)  # 5 секунд на поиск элементов
            
            # Полностью очищаем cookies и кэш перед каждой проверкой
            logger.debug("Очистка cookies и кэша браузера...")
            try:
                # Очищаем cookies с таймаутом (не критично если не получится)
                self.driver.delete_all_cookies()
            except Exception as e:
                logger.debug(f"Не удалось очистить cookies (продолжаем): {e}")
                # Продолжаем работу даже если не удалось очистить cookies
            
            # Очищаем кэш через JavaScript (если страница уже загружена)
            try:
                current_url = self.driver.current_url
                if current_url and current_url != "data:,":
                    self.driver.execute_script("window.localStorage.clear();")
                    self.driver.execute_script("window.sessionStorage.clear();")
            except Exception as e:
                logger.debug(f"Не удалось очистить storage: {e}")
            
            # Жестко обновляем страницу с очисткой кэша
            logger.debug(f"Жесткое обновление страницы: {self.url}")
            # Добавляем timestamp к URL для обхода кэша браузера
            import urllib.parse
            url_with_cache_bust = self.url
            if '?' in url_with_cache_bust:
                url_with_cache_bust += f"&_nocache={int(time.time() * 1000)}"
            else:
                url_with_cache_bust += f"?_nocache={int(time.time() * 1000)}"
            
            # Загружаем страницу с обходом кэша и таймаутом
            try:
                self.driver.set_page_load_timeout(30)
                self.driver.get(url_with_cache_bust)
            except TimeoutException:
                logger.warning("Таймаут при загрузке страницы, пробуем продолжить...")
                # Продолжаем работу даже при таймауте - возможно страница частично загрузилась
            except Exception as e:
                logger.warning(f"Ошибка при загрузке страницы: {e}, пробуем продолжить...")
                # Продолжаем работу даже при ошибке
            
            # Дополнительно очищаем кэш через JavaScript после загрузки
            try:
                self.driver.execute_script("""
                    if ('caches' in window) {
                        caches.keys().then(function(names) {
                            for (let name of names) caches.delete(name);
                        });
                    }
                """)
            except Exception as e:
                logger.debug(f"Не удалось очистить кэш через JS: {e}")
            
            # Ждем полной загрузки страницы (уменьшаем время ожидания)
            time.sleep(2)  # Уменьшаем время ожидания
            
            # Дополнительно ждем, пока страница полностью загрузится (с меньшим таймаутом)
            try:
                WebDriverWait(self.driver, 5).until(
                    lambda driver: driver.execute_script('return document.readyState') == 'complete'
                )
            except TimeoutException:
                logger.warning("Страница загружается дольше ожидаемого, продолжаем...")
                # Продолжаем работу даже если страница не полностью загрузилась
            
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
                print(f"[OK] Элемент на месте! Текст: {current_text[:50]}...")
                # Отправляем уведомление при первой проверке
                self._send_telegram_notification('ok', current_text)
                self.last_ok_notification_time = time.time()
                self.previous_text = current_text
                return True
            
            if current_text != self.previous_text:
                logger.info("Обнаружено изменение текста элемента!")
                logger.info(f"Было: {self.previous_text[:50]}...")
                logger.info(f"Стало: {current_text[:50]}...")
                print("[WARNING] Элемент изменился!")
                
                # Отправляем уведомление
                self._send_telegram_notification('changed', current_text)
                
                # Обновляем предыдущее значение
                self.previous_text = current_text
            else:
                logger.debug("Текст элемента не изменился")
                print("[OK] Элемент на месте!")
                # Отправляем "OK" уведомление периодически (раз в час)
                current_time = time.time()
                if current_time - self.last_ok_notification_time >= self.ok_notification_interval:
                    self._send_telegram_notification('ok', current_text)
                    self.last_ok_notification_time = current_time
            
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
                logger.warning(f"[WARNING] Элемент '{self.expected_text}' не найден на странице!")
                print("[WARNING] Элемент отсутствует!")
                self._send_telegram_notification('missing')
                self.element_found_last_time = False
            else:
                logger.debug(f"Элемент '{self.expected_text}' по-прежнему отсутствует")
                print("[WARNING] Элемент отсутствует!")
            return True
        
        # Элемент найден, проверяем текст
        if self.expected_text.lower() in current_text.lower():
            # Текст соответствует ожидаемому
            current_time = time.time()
            should_send_ok = False
            
            if not self.element_found_last_time:
                # Элемент снова появился - отправляем уведомление
                logger.info(f"[OK] Элемент '{self.expected_text}' снова найден!")
                print("[OK] Элемент на месте!")
                self._send_telegram_notification('found_again', current_text)
                self.last_ok_notification_time = current_time
                should_send_ok = True
            else:
                logger.info(f"[OK] Элемент '{self.expected_text}' присутствует на странице")
                print("[OK] Элемент на месте!")
                
                # Отправляем "OK" уведомление, если прошло достаточно времени с последнего
                if current_time - self.last_ok_notification_time >= self.ok_notification_interval:
                    self._send_telegram_notification('ok', current_text)
                    self.last_ok_notification_time = current_time
                    should_send_ok = True
            
            self.element_found_last_time = True
        else:
            # Текст не соответствует ожидаемому
            logger.warning(f"[WARNING] Элемент найден, но текст изменился!")
            logger.warning(f"Ожидался: '{self.expected_text}'")
            logger.warning(f"Найден: '{current_text}'")
            print(f"[WARNING] Элемент изменился! Ожидался: '{self.expected_text}', найден: '{current_text[:50]}...'")
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
            # В python-telegram-bot 20+ методы асинхронные
            # Создаем новый event loop для каждого вызова
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            async def test_async():
                bot_info = await self.bot.get_me()
                return bot_info.username
            
            if loop.is_running():
                # Если loop уже запущен, используем asyncio.run
                username = asyncio.run(test_async())
            else:
                username = loop.run_until_complete(test_async())
            logger.info(f"Telegram бот подключен: @{username}")
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
                    logger.info(f"Проверка завершена. Следующая проверка через 3 минуты...")
                else:
                    consecutive_errors += 1
                    logger.warning(f"Ошибка при проверке (попытка {consecutive_errors}/{max_consecutive_errors})")
                    
                    # Если слишком много ошибок подряд - перезапускаем драйвер
                    if consecutive_errors >= max_consecutive_errors:
                        logger.warning("Слишком много ошибок подряд. Перезапускаем WebDriver...")
                        self._restart_driver()
                        consecutive_errors = 0
                
                # Ждем 3 минуты (180 секунд) до следующей проверки
                time.sleep(180)
                
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
                        logger.error("Ожидание 3 минут перед следующей попыткой...")
                        time.sleep(180)
        
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

