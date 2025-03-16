import logging
import os
from telegram import Bot
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest
from dotenv import load_dotenv
import json
import asyncio

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
ERROR_CHAT_ID = os.getenv("TELEGRAM_ERROR_CHAT_ID")

# Настройки таймаутов
REQUEST_TIMEOUT = 30

async def send_error_to_telegram(error_message: str, error_data: dict = None):
    """
    Отправляет сообщение об ошибке в Telegram чат
    
    error_message: текст сообщения об ошибке
    error_data: дополнительные данные об ошибке (опционально)
    """
    if not ERROR_CHAT_ID:
        logger.error("TELEGRAM_ERROR_CHAT_ID не установлен в .env файле")
        return False
        
    request = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=REQUEST_TIMEOUT,
        write_timeout=REQUEST_TIMEOUT,
        connect_timeout=REQUEST_TIMEOUT
    )
    bot = Bot(token=TELEGRAM_TOKEN, request=request)
    
    try:
        # Формируем текст сообщения
        message = f"🚨 <b>Ошибка:</b>\n{error_message}"
        
        # Добавляем дополнительные данные, если они есть
        if error_data:
            message += "\n\n<b>Дополнительная информация:</b>\n"
            message += json.dumps(error_data, ensure_ascii=False, indent=2)
            
        await bot.send_message(
            chat_id=ERROR_CHAT_ID,
            text=message,
            parse_mode=ParseMode.HTML
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения об ошибке в Telegram: {e}")
        return False

def send_error(error_message: str, error_data: dict = None):
    """
    Синхронная обертка для отправки сообщения об ошибке
    """
    try:
        return asyncio.run(send_error_to_telegram(error_message, error_data))
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения об ошибке: {e}")
        return False 