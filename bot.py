import asyncio
import logging
from telegram import Bot
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest
import json
import os
from dotenv import load_dotenv
from utils import DateTimeEncoder
import httpx
from telegram.error import TimedOut, TelegramError

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы из переменных окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

# Настройки таймаутов и повторных попыток
MAX_RETRIES = 3
RETRY_DELAY = 5  # секунды
REQUEST_TIMEOUT = 30  # секунды

# Функция для обработки вебхуков от Telegram
def process_update(update):
    """
    Обрабатывает обновления от Telegram, полученные через вебхук
    
    update: объект обновления от Telegram
    """
    try:
        logger.info(f"Получено обновление: {json.dumps(update, cls=DateTimeEncoder)}")
        
        # Здесь можно добавить логику обработки команд или сообщений
        # Например, если это сообщение от пользователя
        if 'message' in update and 'text' in update['message']:
            text = update['message']['text']
            chat_id = update['message']['chat']['id']
            
            # Пример обработки команды
            if text.startswith('/status'):
                asyncio.run(send_message_to_chat(chat_id, "Бот работает нормально!"))
    except Exception as e:
        logger.error(f"Ошибка при обработке обновления: {e}")

# Функция для отправки сообщений в чат
async def send_message_to_chat(chat_id, text, parse_mode=ParseMode.HTML):
    """
    Отправляет сообщение в указанный чат
    
    chat_id: ID чата
    text: текст сообщения
    parse_mode: режим форматирования текста
    """
    try:
        request = HTTPXRequest(connection_pool_size=8, read_timeout=REQUEST_TIMEOUT, write_timeout=REQUEST_TIMEOUT, connect_timeout=REQUEST_TIMEOUT)
        bot = Bot(token=TELEGRAM_TOKEN, request=request)
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        return False

# Класс для публикации статей в Telegram
class TelegramPoster:
    def __init__(self):
        # Создаем HTTPXRequest с увеличенным таймаутом
        self.request = HTTPXRequest(connection_pool_size=8, read_timeout=REQUEST_TIMEOUT, write_timeout=REQUEST_TIMEOUT, connect_timeout=REQUEST_TIMEOUT)
        self.bot = Bot(token=TELEGRAM_TOKEN, request=self.request)
    
    async def post_article(self, article_data, retry_count=0):
        """
        Публикует статью в Telegram канал
        
        article_data: данные статьи (заголовок, текст, ссылка)
        retry_count: счетчик повторных попыток
        """
        try:
            title = article_data.get('title', 'Новая статья')
            summary = article_data.get('summary', 'Нет описания')
            link = article_data.get('link', '')
            image_url = article_data.get('image_url')
            
            # Формируем текст сообщения
            message_text = f"<b>{title}</b>\n\n{summary}\n\n<a href='{link}'>Читать полностью</a>"
            
            # Если есть изображение, отправляем его с подписью
            if image_url:
                try:
                    # Отправляем фото с подписью
                    await self.bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=image_url,
                        caption=message_text,
                        parse_mode=ParseMode.HTML
                    )
                    logger.info(f"Статья '{title}' опубликована с изображением")
                    return True
                except Exception as e:
                    logger.warning(f"Не удалось отправить изображение: {e}. Отправляем только текст.")
                    # Если не удалось отправить изображение, отправляем только текст
                    await self.bot.send_message(
                        chat_id=CHANNEL_ID,
                        text=message_text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=False
                    )
                    logger.info(f"Статья '{title}' опубликована без изображения")
                    return True
            else:
                # Отправляем только текст
                await self.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=message_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False
                )
                logger.info(f"Статья '{title}' опубликована без изображения")
                return True
                
        except (TimedOut, TelegramError) as e:
            # Если произошла ошибка Telegram, пробуем еще раз
            if retry_count < MAX_RETRIES:
                logger.warning(f"Ошибка при публикации статьи в Telegram: {e}. Повторная попытка {retry_count + 1}/{MAX_RETRIES}")
                await asyncio.sleep(RETRY_DELAY)
                return await self.post_article(article_data, retry_count + 1)
            else:
                logger.error(f"Не удалось опубликовать статью после {MAX_RETRIES} попыток: {e}")
                return False
        except Exception as e:
            logger.error(f"Ошибка при публикации статьи в Telegram: {e}")
            return False
    
    async def post_articles_from_queue(self):
        """
        Публикует статьи из очереди на публикацию
        """
        queue_file = "data/publication_queue.json"
        
        if not os.path.exists(queue_file):
            # Убираем лишний лог о пустой очереди
            return
            
        try:
            with open(queue_file, 'r', encoding='utf-8') as f:
                queue = json.load(f)
                
            if not queue:
                # Убираем лишний лог о пустой очереди
                return
                
            # Берем первую статью из очереди
            article = queue.pop(0)
            
            # Публикуем статью
            success = await self.post_article(article)
            
            # Обновляем очередь
            with open(queue_file, 'w', encoding='utf-8') as f:
                json.dump(queue, f, cls=DateTimeEncoder, ensure_ascii=False, indent=2)
                
            if success:
                logger.info(f"Статья '{article['title']}' удалена из очереди после публикации")
                
            return success
                
        except Exception as e:
            logger.error(f"Ошибка при работе с очередью публикаций: {e}")
            return False

# Функция для добавления статьи в очередь публикаций
def add_to_publication_queue(article):
    """
    Добавляет статью в очередь на публикацию
    """
    queue_file = "data/publication_queue.json"
    
    # Создаем директорию, если не существует
    if not os.path.exists("data"):
        os.makedirs("data")
        
    # Загружаем текущую очередь
    queue = []
    if os.path.exists(queue_file):
        try:
            with open(queue_file, 'r', encoding='utf-8') as f:
                queue = json.load(f)
        except json.JSONDecodeError:
            queue = []
    
    # Проверяем, нет ли уже такой статьи в очереди
    if not any(q.get('link') == article.get('link') for q in queue):
        queue.append(article)
        logger.info(f"Статья '{article['title']}' добавлена в очередь на публикацию")
        
        # Сохраняем обновленную очередь
        with open(queue_file, 'w', encoding='utf-8') as f:
            json.dump(queue, f, cls=DateTimeEncoder, ensure_ascii=False, indent=2)
        
        return True
    else:
        # Убираем лишний лог о дубликате
        return False

# Функция для обработки очереди публикаций
async def process_publication_queue():
    """
    Обрабатывает очередь публикаций
    """
    poster = TelegramPoster()
    return await poster.post_articles_from_queue()

# Функция для публикации следующей статьи из очереди
def publish_next_from_queue():
    """
    Публикует следующую статью из очереди
    
    Возвращает:
    - True: если статья была успешно опубликована
    - False: если произошла ошибка
    - None: если очередь пуста
    """
    return asyncio.run(process_publication_queue())

# Функция для обновления очереди публикаций
def update_publication_queue(queue):
    """
    Обновляет очередь публикаций
    """
    queue_file = "data/publication_queue.json"
    
    # Создаем директорию, если не существует
    if not os.path.exists("data"):
        os.makedirs("data")
        
    # Сохраняем обновленную очередь
    with open(queue_file, 'w', encoding='utf-8') as f:
        json.dump(queue, f, cls=DateTimeEncoder, ensure_ascii=False, indent=2) 