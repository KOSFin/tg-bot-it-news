import time
import logging
import os
import threading
from datetime import datetime
import json
from russian_news_sources import get_russian_news_sources
from ai_processor import process_article_with_ai
from bot import add_to_publication_queue, publish_next_from_queue
from utils import DateTimeEncoder
from parse_news import check_news_sources
from process_queue import process_next_article
from background import keep_alive

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Время ожидания между запросами к нейросети (в секундах)
AI_REQUEST_DELAY = 60
# Время ожидания между публикациями (в секундах)
PUBLICATION_DELAY = 10
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
    
    # Добавляем новые статьи в очередь
    for item in news_items:
        # Проверяем, нет ли уже такой статьи в очереди
        if not any(q['link'] == item['link'] for q in queue):
            queue.append(item)
            logger.info(f"Статья '{item['title']}' добавлена в очередь на обработку")
    
    # Сохраняем обновленную очередь
    with open(queue_file, 'w', encoding='utf-8') as f:
        json.dump(queue, f, cls=DateTimeEncoder, ensure_ascii=False, indent=2)
        
    return len(queue)

def get_processing_queue():
    """
    Получает очередь статей на обработку
    """
    queue_file = "data/processing_queue.json"
    
    if not os.path.exists(queue_file):
        return []
        
    try:
        with open(queue_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def update_processing_queue(queue):
    """
    Обновляет очередь статей на обработку
    """
    queue_file = "data/processing_queue.json"
    
    # Создаем директорию, если не существует
    if not os.path.exists("data"):
        os.makedirs("data")
        
    # Сохраняем обновленную очередь
    with open(queue_file, 'w', encoding='utf-8') as f:
        json.dump(queue, f, cls=DateTimeEncoder, ensure_ascii=False, indent=2)

def process_next_article():
    """
    Обрабатывает следующую статью из очереди с помощью нейросети
    
    Возвращает:
    - True: если статья была успешно обработана нейросетью
    - False: если очередь пуста или произошла ошибка
    - "already_processed": если статья уже была обработана ранее
    """
    # Получаем очередь статей
    queue = get_processing_queue()
    
    if not queue:
        logger.info("Очередь на обработку пуста")
        return False
        
    # Берем первую статью из очереди
    article = queue.pop(0)
    
    # Обрабатываем статью с помощью нейросети
    logger.info(f"Обработка статьи '{article['title']}' нейросетью")
    ai_response = process_article_with_ai(article)
    
    # Обновляем очередь
    update_processing_queue(queue)
    
    # Если ai_response равен None, значит статья уже была обработана ранее
    if ai_response is None:
        logger.info(f"Статья '{article['title']}' уже была обработана ранее")
        return "already_processed"
    
    # Если статья одобрена, добавляем её в очередь на публикацию
    if ai_response and ai_response.get('approved'):
        logger.info(f"Статья '{article['title']}' одобрена нейросетью")
        
        # Проверяем, есть ли необходимые поля для публикации
        if 'summary' in ai_response:
            # Подготавливаем данные для публикации
            publication_data = {
                'title': ai_response.get('title', article['title']),
                'summary': ai_response['summary'].replace('[ССЫЛКА]', ''),
                'link': article['link'],
                'image_url': article.get('image_url')
            }
            
            # Добавляем в очередь на публикацию
            add_to_publication_queue(publication_data)
            return True
        else:
            logger.warning(f"Статья '{article['title']}' одобрена, но отсутствует поле 'summary'")
            return True
    else:
        if ai_response:
            logger.info(f"Статья '{article['title']}' отклонена нейросетью: {ai_response.get('reason')}")
        else:
            logger.info(f"Статья '{article['title']}' не обработана из-за ошибки")
        return True  # Возвращаем True, так как статья была обработана, даже если она была отклонена

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
            
            # Выводим заголовки в консоль
            for news in latest_news:
                print(f"[{source.name}] {news['title']}")
                print(f"Ссылка: {news['link']}")
                print("-" * 50)
        
        source.update_last_check()
        time.sleep(1)  # Небольшая пауза между запросами к разным источникам
    
    # Сохраняем новые статьи в очередь на обработку
    if all_news:
        queue_size = save_to_processing_queue(all_news)
        logger.info(f"В очереди на обработку {queue_size} статей")
    else:
        logger.info("Новых статей не найдено")

def news_parser_thread(stop_event):
    """
    Поток для парсинга новостей
    """
    logger.info("Запуск потока парсинга новостей")
    
    try:
        while not stop_event.is_set():
            # Проверяем новости из источников
            check_news_sources()
            
            # Пауза перед следующей проверкой
            logger.info(f"Ожидание {NEWS_CHECK_DELAY} секунд до следующей проверки...")
            time.sleep(NEWS_CHECK_DELAY)
            
    except Exception as e:
        logger.error(f"Ошибка в потоке парсинга новостей: {e}")

def ai_processor_thread(stop_event):
    """
    Поток для обработки статей нейросетью
    """
    logger.info("Запуск потока обработки статей нейросетью")
    
    try:
        while not stop_event.is_set():
            # Обрабатываем следующую статью из очереди
            result = process_next_article()
            
            if result is True:
                # Если статья была обработана нейросетью, делаем паузу перед следующей
                logger.info(f"Ожидание {AI_REQUEST_DELAY} секунд до следующей обработки...")
                time.sleep(AI_REQUEST_DELAY)
            elif result is False:
                # Если очередь пуста, делаем небольшую паузу и проверяем снова
                time.sleep(10)
            elif result == "already_processed":
                # Если статья уже была обработана ранее, сразу переходим к следующей без кулдауна
                continue
            
    except Exception as e:
        logger.error(f"Ошибка в потоке обработки статей: {e}")

def publisher_worker(stop_event):
    """
    Поток для публикации статей
    """
    logger.info("Запуск потока публикации статей")
    
    # Счетчик неудачных попыток публикации
    failed_publication_attempts = 0
    
    try:
        while not stop_event.is_set():
            try:
                # Публикуем следующую статью из очереди на публикацию
                publication_result = publish_next_from_queue()
                
                if publication_result is True:
                    # Сбрасываем счетчик при успешной публикации
                    failed_publication_attempts = 0
                    logger.info(f"Статья успешно опубликована. Ожидание {PUBLICATION_DELAY} секунд до следующей публикации...")
                elif publication_result is False:
                    failed_publication_attempts += 1
                    logger.warning(f"Неудачная попытка публикации #{failed_publication_attempts}")
                    
                    # Если было несколько неудачных попыток подряд, увеличиваем время ожидания
                    if failed_publication_attempts >= 3:
                        logger.warning("Слишком много неудачных попыток публикации. Увеличиваем время ожидания.")
                        time.sleep(60)  # Дополнительная минута ожидания
                        failed_publication_attempts = 0
                else:
                    # Если очередь пуста, делаем паузу
                    time.sleep(PUBLICATION_DELAY * 3)  # Увеличенная пауза, если очередь пуста
                    continue
                    
            except Exception as e:
                logger.error(f"Ошибка при публикации статьи: {e}")
                failed_publication_attempts += 1
            
            # Пауза между публикациями
            time.sleep(PUBLICATION_DELAY)
            
    except Exception as e:
        logger.error(f"Ошибка в потоке публикации статей: {e}")

def main():
    """
    Основная функция для запуска всех потоков
    """
    logger.info("Запуск системы мониторинга русскоязычных IT-новостей")
    
    # Создаем событие для остановки потоков
    stop_event = threading.Event()
    
    # Запускаем Flask-сервер в отдельном потоке
    keep_alive()
    
    try:
        # Создаем и запускаем потоки
        news_thread = threading.Thread(target=news_parser_thread, args=(stop_event,))
        ai_thread = threading.Thread(target=ai_processor_thread, args=(stop_event,))
        publisher_thread = threading.Thread(target=publisher_worker, args=(stop_event,))
        
        news_thread.start()
        ai_thread.start()
        publisher_thread.start()
        
        # Ждем завершения потоков
        news_thread.join()
        ai_thread.join()
        publisher_thread.join()
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки. Завершаем работу...")
        stop_event.set()
        
        # Ждем завершения потоков
        news_thread.join()
        ai_thread.join()
        publisher_thread.join()
        
    logger.info("Программа завершена")

if __name__ == "__main__":
    main() 