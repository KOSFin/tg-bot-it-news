import time
import logging
import os
from datetime import datetime
import json
from russian_news_sources import get_russian_news_sources
from utils import DateTimeEncoder

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Время ожидания между проверками новостей (в секундах)
NEWS_CHECK_DELAY = 300

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

def check_news_sources():
    """
    Проверяет новости из всех источников и добавляет их в очередь на обработку
    """
    logger.info("Запуск проверки новостей из источников")
    
    # Получаем список источников новостей
    news_sources = get_russian_news_sources()
    logger.info(f"Загружено {len(news_sources)} источников новостей")
    
    all_news = []
    
    # Проверяем новости из всех источников
    for source in news_sources:
        logger.info(f"Проверка новостей из источника: {source.name}")
        latest_news = source.get_latest_news()
        
        if latest_news:
            logger.info(f"Найдено {len(latest_news)} новых статей из {source.name}")
            all_news.extend(latest_news)
            
            # Выводим только первые 3 заголовка в консоль для каждого источника
            for i, news in enumerate(latest_news[:3]):
                print(f"[{source.name}] {news['title']}")
                print(f"Ссылка: {news['link']}")
                print("-" * 50)
            
            # Если статей больше 3, выводим сообщение о количестве остальных
            if len(latest_news) > 3:
                print(f"... и еще {len(latest_news) - 3} статей из {source.name}")
                print("-" * 50)
        
        source.update_last_check()
        time.sleep(1)  # Небольшая пауза между запросами к разным источникам
    
    # Сохраняем новые статьи в очередь на обработку
    if all_news:
        queue_size = save_to_processing_queue(all_news)
        logger.info(f"В очереди на обработку {queue_size} статей")
    else:
        logger.info("Новых статей не найдено")

def main():
    """
    Основная функция для парсинга новостей
    """
    logger.info("Запуск системы мониторинга русскоязычных IT-новостей")
    
    # Проверяем, первый ли это запуск
    first_run = not os.path.exists('data/last_check.txt')
    
    try:
        while True:
            # Проверяем новости из источников
            check_news_sources()
            
            # Пауза перед следующей проверкой
            logger.info(f"Ожидание {NEWS_CHECK_DELAY} секунд до следующей проверки...")
            time.sleep(NEWS_CHECK_DELAY)
            
    except KeyboardInterrupt:
        logger.info("Программа остановлена пользователем")
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}")

if __name__ == "__main__":
    main() 