import json
import re
import logging
import os
from datetime import datetime
from bot import add_to_publication_queue

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Пути к файлам
PROCESSED_ARTICLES_LOG = "data/processed_articles.json"
APPROVED_ARTICLES_LOG = "data/approved_articles.json"

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super(DateTimeEncoder, self).default(obj)

def get_processed_articles():
    """
    Получает список обработанных статей
    """
    if not os.path.exists(PROCESSED_ARTICLES_LOG):
        return []
        
    try:
        with open(PROCESSED_ARTICLES_LOG, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.error(f"Ошибка при чтении файла {PROCESSED_ARTICLES_LOG}")
        return []

def save_approved_article(article):
    """
    Сохраняет одобренную статью в лог
    """
    # Создаем директорию, если не существует
    if not os.path.exists("data"):
        os.makedirs("data")
        
    # Создаем файл, если не существует
    if not os.path.exists(APPROVED_ARTICLES_LOG):
        with open(APPROVED_ARTICLES_LOG, 'w', encoding='utf-8') as f:
            json.dump([], f)
    
    # Загружаем текущий список одобренных статей
    approved_articles = []
    try:
        with open(APPROVED_ARTICLES_LOG, 'r', encoding='utf-8') as f:
            approved_articles = json.load(f)
    except json.JSONDecodeError:
        approved_articles = []
    
    # Проверяем, нет ли уже такой статьи в списке
    if not any(a['link'] == article['link'] for a in approved_articles):
        approved_articles.append(article)
        
        # Сохраняем обновленный список
        with open(APPROVED_ARTICLES_LOG, 'w', encoding='utf-8') as f:
            json.dump(approved_articles, f, cls=DateTimeEncoder, ensure_ascii=False, indent=2)
            
        logger.info(f"Статья '{article['title']}' добавлена в лог одобренных статей")
    else:
        logger.info(f"Статья '{article['title']}' уже есть в логе одобренных статей")

def extract_data_from_raw_response(raw_response):
    """
    Извлекает данные из raw_response с помощью регулярных выражений
    """
    # Создаем словарь для хранения извлеченных данных
    extracted_data = {"error": "JSON parsing error", "raw_response": raw_response}
    
    # Проверяем, есть ли в ответе "approved": true
    approved_match = re.search(r'"approved":\s*true', raw_response)
    if approved_match:
        extracted_data["approved"] = True
        
        # Пытаемся извлечь summary
        summary_match = re.search(r'"summary":\s*"([^"]*(?:"[^"]*"[^"]*)*)"', raw_response)
        if summary_match:
            extracted_data["summary"] = summary_match.group(1).replace('\\"', '"')
        
        # Пытаемся извлечь title
        title_match = re.search(r'"title":\s*"([^"]*(?:"[^"]*"[^"]*)*)"', raw_response)
        if title_match:
            extracted_data["title"] = title_match.group(1).replace('\\"', '"')
        
        # Пытаемся извлечь reason
        reason_match = re.search(r'"reason":\s*"([^"]*(?:"[^"]*"[^"]*)*)"', raw_response)
        if reason_match:
            extracted_data["reason"] = reason_match.group(1).replace('\\"', '"')
        
        logger.info(f"Извлечены данные из ответа нейросети: {extracted_data}")
    
    return extracted_data

def process_articles_with_json_errors():
    """
    Обрабатывает статьи с ошибками парсинга JSON и добавляет их в очередь публикации,
    если они были одобрены нейросетью
    """
    # Получаем список обработанных статей
    processed_articles = get_processed_articles()
    
    # Счетчики для статистики
    fixed_count = 0
    error_count = 0
    
    # Обрабатываем каждую статью
    for article in processed_articles:
        # Проверяем, есть ли у статьи ошибка парсинга JSON
        if 'ai_decision' in article and 'error' in article['ai_decision'] and article['ai_decision']['error'] == 'JSON parsing error':
            logger.info(f"Обработка статьи с ошибкой парсинга JSON: {article['title']}")
            
            # Извлекаем данные из raw_response
            raw_response = article['ai_decision'].get('raw_response', '')
            extracted_data = extract_data_from_raw_response(raw_response)
            
            # Если статья одобрена и есть необходимые поля для публикации
            if extracted_data.get('approved') and 'summary' in extracted_data and 'title' in extracted_data:
                logger.info(f"Статья '{article['title']}' одобрена нейросетью")
                
                # Подготавливаем данные для публикации
                publication_data = {
                    'title': extracted_data.get('title', article['title']),
                    'summary': extracted_data['summary'].replace('[ССЫЛКА]', ''),
                    'link': article['link'],
                    'image_url': article.get('image_url')
                }
                
                # Добавляем в очередь на публикацию
                add_to_publication_queue(publication_data)
                
                # Сохраняем статью в лог одобренных
                approved_article = {
                    'title': extracted_data.get('title', article['title']),
                    'summary': extracted_data['summary'],
                    'link': article['link'],
                    'source': article['source'],
                    'image_url': article.get('image_url'),
                    'approved_at': datetime.now().isoformat()
                }
                save_approved_article(approved_article)
                
                fixed_count += 1
            else:
                logger.info(f"Статья '{article['title']}' не может быть добавлена в очередь публикации: отсутствуют необходимые данные")
                error_count += 1
    
    logger.info(f"Обработка завершена. Исправлено статей: {fixed_count}, ошибок: {error_count}")
    return fixed_count, error_count

if __name__ == "__main__":
    logger.info("Запуск обработки статей с ошибками парсинга JSON")
    fixed_count, error_count = process_articles_with_json_errors()
    logger.info(f"Обработка завершена. Исправлено статей: {fixed_count}, ошибок: {error_count}") 