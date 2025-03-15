import logging
from russian_news_sources import DeCenterNewsSource
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """
    Тестирование класса DeCenterNewsSource
    """
    logger.info("Запуск теста DeCenterNewsSource")
    
    # Создаем экземпляр класса
    source = DeCenterNewsSource()
    
    # Устанавливаем дату последней проверки на неделю назад, чтобы все статьи считались новыми
    source.last_check = datetime.now() - timedelta(days=7)
    
    # Получаем новости
    news = source.get_latest_news()
    
    # Выводим результаты
    logger.info(f"Получено {len(news)} новостей из DeCenter")
    
    # Выводим заголовки новостей
    for i, article in enumerate(news):
        logger.info(f"Статья {i+1}: {article['title']}")
        logger.info(f"Ссылка: {article['link']}")
        logger.info("-" * 50)

if __name__ == "__main__":
    main() 