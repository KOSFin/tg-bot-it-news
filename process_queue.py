import time
import logging
import os
from datetime import datetime
import json
from ai_processor import process_article_with_ai
from bot import add_to_publication_queue
from utils import DateTimeEncoder

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Время ожидания между запросами к нейросети (в секундах)
AI_REQUEST_DELAY = 10

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
        # Убираем лишний лог о пустой очереди
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
        # Убираем лишний лог о ранее обработанной статье
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
                'image_url': article.get('image_url'),
                'ai_decision': {
                    'tags': ai_response.get('tags', []),
                    'approved': True
                }
            }
            
            # Проверяем теги
            if 'tags' not in ai_response or not ai_response['tags']:
                logger.warning(f"Статья '{article['title']}' не содержит тегов, добавляем стандартный тег")
                publication_data['ai_decision']['tags'] = ["#IT"]
            
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
            logger.error(f"Статья '{article['title']}' не обработана из-за ошибки")
        return True  # Возвращаем True, так как статья была обработана, даже если она была отклонена

def get_processed_articles():
    """
    Получает список уже обработанных статей
    """
    processed_file = "data/processed_articles.json"
    
    if not os.path.exists(processed_file):
        return []
        
    try:
        with open(processed_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def add_to_processed_articles(article_link):
    """
    Добавляет статью в список обработанных
    """
    processed_file = "data/processed_articles.json"
    
    # Создаем директорию, если не существует
    if not os.path.exists("data"):
        os.makedirs("data")
        
    # Загружаем текущий список обработанных статей
    processed = get_processed_articles()
    
    # Добавляем новую статью, если её ещё нет в списке
    if article_link not in processed:
        processed.append(article_link)
        
        # Сохраняем обновленный список
        with open(processed_file, 'w', encoding='utf-8') as f:
            json.dump(processed, f, ensure_ascii=False, indent=2)
        
        return True
    
    return False

def is_article_processed(article_link):
    """
    Проверяет, была ли статья уже обработана
    """
    processed = get_processed_articles()
    return article_link in processed 