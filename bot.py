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
            
            # Можно добавить другие команды по необходимости
            
        return True
    except Exception as e:
        logger.error(f"Ошибка при обработке обновления: {e}")
        return False

# Функция для отправки сообщения в чат
async def send_message_to_chat(chat_id, text, parse_mode=ParseMode.HTML):
    """
    Отправляет сообщение в указанный чат
    
    chat_id: ID чата
    text: текст сообщения
    parse_mode: режим форматирования текста
    """
    request = HTTPXRequest(connection_pool_size=8, read_timeout=REQUEST_TIMEOUT, write_timeout=REQUEST_TIMEOUT, connect_timeout=REQUEST_TIMEOUT)
    bot = Bot(token=TELEGRAM_TOKEN, request=request)
    
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        return False

class TelegramPoster:
    def __init__(self):
        # Создаем HTTPXRequest с увеличенным таймаутом
        request = HTTPXRequest(connection_pool_size=8, read_timeout=REQUEST_TIMEOUT, write_timeout=REQUEST_TIMEOUT, connect_timeout=REQUEST_TIMEOUT)
        self.bot = Bot(token=TELEGRAM_TOKEN, request=request)
        
    async def post_article(self, article_data, retry_count=0):
        """
        Публикует статью в Telegram канал
        
        article_data: словарь с данными статьи:
            - title: заголовок статьи
            - summary: краткое содержание статьи
            - link: ссылка на оригинал
            - image_url: ссылка на изображение (может быть None)
        retry_count: текущее количество повторных попыток
        """
        try:
            # Формируем текст сообщения
            message_text = f"<b>{article_data['title']}</b>\n\n"
            message_text += article_data['summary']
            
            # Добавляем ссылку на оригинал, если она есть
            if article_data.get('link'):
                message_text += f"\n\n<a href='{article_data['link']}'>Читать полностью</a>"
            
            # Добавляем теги, если они есть
            if article_data.get('tags') and len(article_data['tags']) > 0:
                message_text += "\n\n"
                # Убедимся, что теги начинаются с #
                formatted_tags = []
                for tag in article_data['tags']:
                    if tag.startswith('#'):
                        formatted_tags.append(tag)
                    else:
                        formatted_tags.append(f"#{tag}")
                message_text += " ".join(formatted_tags)
                logger.info(f"Добавлены теги: {formatted_tags}")
            
            # Если есть изображение, отправляем с ним
            if article_data.get('image_url'):
                await self.bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=article_data['image_url'],
                    caption=message_text,
                    parse_mode=ParseMode.HTML
                )
            else:
                # Иначе отправляем просто текст
                await self.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=message_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False
                )
                
            logger.info(f"Статья '{article_data['title']}' успешно опубликована в Telegram")
            return True
            
        except (TimedOut, asyncio.TimeoutError) as e:
            # Обработка таймаута
            if retry_count < MAX_RETRIES:
                retry_count += 1
                logger.warning(f"Таймаут при публикации статьи. Повторная попытка {retry_count}/{MAX_RETRIES} через {RETRY_DELAY} секунд...")
                await asyncio.sleep(RETRY_DELAY)
                return await self.post_article(article_data, retry_count)
            else:
                logger.error(f"Ошибка при публикации статьи в Telegram после {MAX_RETRIES} попыток: {e}")
                return False
        except TelegramError as e:
            logger.error(f"Ошибка Telegram API при публикации статьи: {e}")
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
            logger.info("Очередь публикаций пуста")
            return
            
        try:
            with open(queue_file, 'r', encoding='utf-8') as f:
                queue = json.load(f)
                
            if not queue:
                logger.info("Очередь публикаций пуста")
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
    
    # Проверяем, есть ли теги в статье и корректно ли они представлены
    if 'tags' not in article or not article['tags']:
        article['tags'] = []
    elif not isinstance(article['tags'], list):
        # Если теги не в виде списка, преобразуем их
        if isinstance(article['tags'], str):
            article['tags'] = [article['tags']]
        else:
            article['tags'] = []
            logger.warning(f"Теги для статьи '{article['title']}' имеют неверный формат и были сброшены")
    
    # Проверяем, нет ли уже такой статьи в очереди
    if not any(q['link'] == article['link'] for q in queue):
        queue.append(article)
        logger.info(f"Статья '{article['title']}' добавлена в очередь на публикацию с тегами: {article['tags']}")
    
    # Сохраняем обновленную очередь
    with open(queue_file, 'w', encoding='utf-8') as f:
        json.dump(queue, f, cls=DateTimeEncoder, ensure_ascii=False, indent=2)
        
    return len(queue)

# Асинхронная функция для запуска публикации из очереди
async def process_publication_queue():
    """
    Обрабатывает очередь публикаций
    """
    poster = TelegramPoster()
    try:
        return await poster.post_articles_from_queue()
    except Exception as e:
        logger.error(f"Ошибка при обработке очереди публикаций: {e}")
        return False

# Функция для запуска обработки очереди из синхронного кода
def publish_next_from_queue():
    """
    Публикует следующую статью из очереди
    
    Возвращает:
    - True: если статья успешно опубликована
    - False: если произошла ошибка или очередь пуста
    """
    try:
        return asyncio.run(process_publication_queue())
    except Exception as e:
        logger.error(f"Ошибка при публикации из очереди: {e}")
        return False

def update_publication_queue(queue):
    """
    Обновляет очередь статей на публикацию
    """
    queue_file = "data/publication_queue.json"
    
    # Создаем директорию, если не существует
    if not os.path.exists("data"):
        os.makedirs("data")
        
    # Сохраняем обновленную очередь
    with open(queue_file, 'w', encoding='utf-8') as f:
        json.dump(queue, f, cls=DateTimeEncoder, ensure_ascii=False, indent=2) 