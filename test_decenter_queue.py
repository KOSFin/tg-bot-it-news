import logging
import os
import json
from russian_news_sources import DeCenterNewsSource
from utils import DateTimeEncoder

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def save_to_processing_queue(news_items):
    """
    Сохраняет новости в очередь на обработку нейросетью
    """
    queue_file = "data/processing_queue.json"
    
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
    
    # Подсчитываем количество добавленных статей
    added_count = 0
    
    # Добавляем новые статьи в очередь
    for item in news_items:
        # Проверяем, нет ли уже такой статьи в очереди
        if not any(q['link'] == item['link'] for q in queue):
            queue.append(item)
            added_count += 1
    
    # Выводим общую информацию о добавленных статьях
    if added_count > 0:
        logger.info(f"Добавлено {added_count} новых статей в очередь на обработку")
    
    # Сохраняем обновленную очередь
    with open(queue_file, 'w', encoding='utf-8') as f:
        json.dump(queue, f, cls=DateTimeEncoder, ensure_ascii=False, indent=2)
        
    return len(queue)

def main():
    """
    Тестирование добавления статей из DeCenter в очередь
    """
    logger.info("Запуск теста добавления статей из DeCenter в очередь")
    
    # Создаем экземпляр класса
    source = DeCenterNewsSource()
    
    # Получаем новости
    news = source.get_latest_news()
    
    # Выводим результаты
    logger.info(f"Получено {len(news)} статей из DeCenter")
    
    # Выводим заголовки новостей
    for i, article in enumerate(news[:3]):
        logger.info(f"Статья {i+1}: {article['title']}")
        logger.info(f"Ссылка: {article['link']}")
        logger.info("-" * 50)
    
    # Если статей больше 3, выводим сообщение о количестве остальных
    if len(news) > 3:
        logger.info(f"... и еще {len(news) - 3} статей")
    
    # Добавляем статьи в очередь
    queue_size = save_to_processing_queue(news)
    logger.info(f"В очереди на обработку {queue_size} статей")

if __name__ == "__main__":
    main() 