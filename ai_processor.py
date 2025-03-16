import logging
import json
import os
import re
from groq import Groq
import time
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from utils import DateTimeEncoder
from error_handler import send_error_to_telegram

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация клиента Groq с API ключом из переменных окружения
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Файлы для хранения данных
APPROVED_ARTICLES_LOG = "data/approved_articles.json"
PROCESSED_ARTICLES_LOG = "data/processed_articles.json"
# Максимальный возраст статей в логах (в днях)
MAX_ARTICLE_AGE_DAYS = 3

def get_approved_articles():
    """
    Получает список одобренных статей из лога
    """
    if not os.path.exists(APPROVED_ARTICLES_LOG):
        return []
        
    try:
        with open(APPROVED_ARTICLES_LOG, 'r', encoding='utf-8') as f:
            articles = json.load(f)
            # Фильтруем статьи по возрасту
            return filter_articles_by_age(articles)
    except json.JSONDecodeError:
        return []

def filter_articles_by_age(articles):
    """
    Фильтрует статьи по возрасту, оставляя только те, которые не старше MAX_ARTICLE_AGE_DAYS
    """
    current_time = datetime.now()
    filtered_articles = []
    
    for article in articles:
        # Проверяем наличие даты одобрения
        if 'approved_at' in article:
            try:
                approved_at = datetime.fromisoformat(article['approved_at'])
                # Если статья не старше MAX_ARTICLE_AGE_DAYS дней, добавляем её в отфильтрованный список
                if (current_time - approved_at).days <= MAX_ARTICLE_AGE_DAYS:
                    filtered_articles.append(article)
            except (ValueError, TypeError):
                # Если не удалось распарсить дату, оставляем статью (на всякий случай)
                filtered_articles.append(article)
        else:
            # Если нет даты одобрения, оставляем статью (на всякий случай)
            filtered_articles.append(article)
    
    # Если количество отфильтрованных статей отличается от исходного, сохраняем отфильтрованный список
    if len(filtered_articles) != len(articles):
        logger.info(f"Удалено {len(articles) - len(filtered_articles)} устаревших статей из лога одобренных")
        save_filtered_articles(filtered_articles, APPROVED_ARTICLES_LOG)
    
    return filtered_articles

def get_processed_articles():
    """
    Получает список всех обработанных статей из лога
    """
    if not os.path.exists(PROCESSED_ARTICLES_LOG):
        return []
        
    try:
        with open(PROCESSED_ARTICLES_LOG, 'r', encoding='utf-8') as f:
            articles = json.load(f)
            # Фильтруем статьи по возрасту
            return filter_articles_by_age(articles)
    except json.JSONDecodeError:
        return []

def save_filtered_articles(articles, file_path):
    """
    Сохраняет отфильтрованный список статей в указанный файл
    """
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(articles, f, cls=DateTimeEncoder, ensure_ascii=False, indent=2)

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
    approved_articles = get_approved_articles()
    
    # Проверяем, есть ли теги в статье и корректно ли они представлены
    if 'tags' not in article or article['tags'] is None:
        article['tags'] = []
        logger.warning(f"Статья '{article['title']}' не содержит тегов")
    elif not isinstance(article['tags'], list):
        # Если теги не в виде списка, преобразуем их
        if isinstance(article['tags'], str):
            article['tags'] = [article['tags']]
        else:
            article['tags'] = []
            logger.warning(f"Теги для статьи '{article['title']}' имеют неверный формат и были сброшены")
    
    # Добавляем новую статью
    approved_articles.append(article)
    
    # Сохраняем обновленный список
    with open(APPROVED_ARTICLES_LOG, 'w', encoding='utf-8') as f:
        json.dump(approved_articles, f, cls=DateTimeEncoder, ensure_ascii=False, indent=2)
        
    logger.info(f"Статья '{article['title']}' добавлена в лог одобренных статей с тегами: {article['tags']}")

def save_processed_article(article, ai_response=None):
    """
    Сохраняет обработанную статью в лог
    """
    # Создаем директорию, если не существует
    if not os.path.exists("data"):
        os.makedirs("data")
        
    # Создаем файл, если не существует
    if not os.path.exists(PROCESSED_ARTICLES_LOG):
        with open(PROCESSED_ARTICLES_LOG, 'w', encoding='utf-8') as f:
            json.dump([], f)
    
    # Загружаем текущий список обработанных статей
    processed_articles = get_processed_articles()
    
    # Добавляем информацию о решении ИИ
    if ai_response:
        article['ai_decision'] = ai_response
        article['processed_at'] = datetime.now().isoformat()
    
    # Добавляем новую статью
    processed_articles.append(article)
    
    # Сохраняем обновленный список
    with open(PROCESSED_ARTICLES_LOG, 'w', encoding='utf-8') as f:
        json.dump(processed_articles, f, cls=DateTimeEncoder, ensure_ascii=False, indent=2)
        
    logger.info(f"Статья '{article['title']}' добавлена в лог обработанных статей")

def is_article_processed(article_link):
    """
    Проверяет, была ли статья уже обработана
    """
    processed_articles = get_processed_articles()
    return any(article['link'] == article_link for article in processed_articles)

def parse_decenter_channel():
    """
    Парсит финансовый канал DeCenter и возвращает список последних статей
    """
    url = "https://t.me/s/DeCenter"
    logger.info(f"Парсинг канала DeCenter: {url}")
    
    try:
        # Отправляем запрос к странице канала
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        response.raise_for_status()
        
        # Парсим HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Находим все сообщения
        messages = soup.find_all('div', class_='tgme_widget_message')
        
        articles = []
        
        for message in messages:
            try:
                # Получаем текст сообщения
                message_text_div = message.find('div', class_='tgme_widget_message_text')
                if not message_text_div:
                    continue
                
                content = message_text_div.get_text(strip=True)
                
                # Получаем ссылку на сообщение
                link = message.find('a', class_='tgme_widget_message_date')['href'] if message.find('a', class_='tgme_widget_message_date') else None
                
                # Получаем дату сообщения
                date_str = message.find('time', class_='time')['datetime'] if message.find('time', class_='time') else None
                
                # Получаем изображение, если есть
                image_url = None
                photo_div = message.find('a', class_='tgme_widget_message_photo_wrap')
                if photo_div and 'style' in photo_div.attrs:
                    style = photo_div['style']
                    image_match = re.search(r'background-image:url\([\'"](.+?)[\'"]\)', style)
                    if image_match:
                        image_url = image_match.group(1)
                
                # Формируем заголовок из первых 100 символов текста
                title = content[:100] + ('...' if len(content) > 100 else '')
                
                # Создаем объект статьи
                article = {
                    'title': title,
                    'content': content,
                    'link': link,
                    'source': 'DeCenter',
                    'image_url': image_url,
                    'published_at': date_str
                }
                
                articles.append(article)
                
            except Exception as e:
                logger.error(f"Ошибка при парсинге сообщения: {e}")
        
        logger.info(f"Получено {len(articles)} сообщений из канала DeCenter")
        return articles
        
    except Exception as e:
        logger.error(f"Ошибка при парсинге канала DeCenter: {e}")
        return []

def process_article_with_ai(article):
    """
    Обрабатывает статью с помощью нейросети
    
    article: словарь с данными статьи:
        - title: заголовок статьи
        - content: содержание статьи
        - link: ссылка на статью
        - source: источник статьи
        - image_url: ссылка на изображение (может быть None)
    
    Возвращает результат обработки в формате JSON или None в случае ошибки
    """
    # Проверяем, была ли статья уже обработана
    if is_article_processed(article['link']):
        return None
    
    # Получаем список одобренных статей для проверки на дубликаты
    approved_articles = get_approved_articles()
    
    # Формируем промпт для нейросети
    prompt = f"""
Ты - модератор IT-новостного Telegram канала. Твоя задача - проанализировать статью и решить, стоит ли публиковать её в канале.

Статья для анализа:
Заголовок: {article['title']}
Источник: {article['source']}
Ссылка: {article['link']}
Содержание: {article['content']}

Список уже опубликованных статей:
{json.dumps([{'title': a['title'], 'link': a['link']} for a in approved_articles], ensure_ascii=False, indent=2)}

Твоя задача:
1. Проверить, что статья на русском языке или содержит важную информацию для русскоязычной аудитории
2. Проверить, что статья не дублирует уже опубликованные (по содержанию, а не только по заголовку)
3. Оценить важность и актуальность статьи для IT-сообщества
4. Создать максимально полное и информативное описание статьи для публикации в Telegram
5. Присвоить статье один или несколько тегов из списка доступных тегов

Статья должна соответствовать следующим критериям:
- Быть на русском языке или содержать важную информацию для русскоязычной аудитории
- Содержать важные IT-новости, полезные гайды, новости крупных технологических компаний или информацию о значимых личностях в IT-сфере
- Не содержать вбросов, фейков или неподтвержденной информации
- Не дублировать уже опубликованные статьи по содержанию

ВАЖНО: Принимай также новости о значимых личностях в IT-сфере, таких как Павел Дуров, Илон Маск, руководители крупных технологических компаний, а также новости об обновлениях популярных сервисов и приложений (например, Telegram, VK, Яндекс и т.д.).

ВАЖНО: НЕ публикуй статьи и новости, которые интересны только узкому кругу IT-специалистов, например:
- Мелкие обновления в языках программирования (Go, Rust, Python и т.д.), если они не меняют кардинально возможности языка
- Узкоспециализированные технические гайды, интересные только разработчикам конкретной технологии
- Инструкции по ремонту техники и другие бытовые советы
- Обзоры нишевых инструментов, используемых малым количеством специалистов

Публикуй только контент, который может быть интересен широкой IT-аудитории:
- Научные открытия и прорывы в технологиях
- Новости крупных IT-корпораций (Apple, Google, Microsoft, Meta и т.д.)
- Значимые события в сфере искусственного интеллекта и машинного обучения
- Важные обновления популярных сервисов и приложений
- Новости кибербезопасности, затрагивающие большое количество пользователей
- Анонсы и релизы популярных продуктов

ВАЖНО о финансовых новостях: публикуй ТОЛЬКО САМЫЕ КРУПНЫЕ И ЗНАЧИМЫЕ финансовые новости, такие как:
- Значительные изменения курса основных мировых валют (доллар, евро, юань)
- Существенные изменения цены золота, нефти и других ключевых биржевых товаров
- Резкие и значительные изменения курса основных криптовалют (только Bitcoin, Ethereum, TON)
- Крупные финансовые кризисы, влияющие на глобальную экономику
- Важные изменения в финансовом регулировании, влияющие на IT-сферу
НЕ публикуй новости о малоизвестных криптовалютах, незначительных колебаниях курсов, мелких инвестициях и неизвестных личностях в финансовой сфере.

СИСТЕМА ТЕГОВ:
Для каждой статьи необходимо выбрать один или несколько тегов из следующего списка:
1. #ИИ - новости об искусственном интеллекте, нейросетях, машинном обучении
2. #Финансы - крупные финансовые новости, связанные с IT-сферой
3. #Безопасность - новости о кибербезопасности, уязвимостях, хакерских атаках
4. #Гаджеты - новости о новых устройствах, гаджетах, железе
5. #Разработка - важные новости для разработчиков, новые технологии и инструменты
6. #Соцсети - новости о социальных сетях и мессенджерах
7. #Компании - новости о крупных IT-компаниях
8. #Интернет - новости о развитии интернета, веб-технологий
9. #Игры - новости из мира игровой индустрии
10. #Инструкция - полезные гайды и инструкции
11. #Россия - новости, связанные с российским IT-сектором
12. #Законы - новости о законодательстве в сфере IT

ИНСТРУКЦИИ ПО СОЗДАНИЮ ОПИСАНИЯ:

ГЛАВНАЯ ЦЕЛЬ: Создать настолько полное и информативное описание, чтобы пользователю НЕ ТРЕБОВАЛОСЬ переходить по ссылке для получения всей важной информации.

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА:
- НИКОГДА не упоминай автора статьи или фразы вроде "Автор рассказывает...", "В статье говорится..."
- НИКОГДА не дублируй заголовок в тексте описания - он будет добавлен автоматически
- НИКОГДА не используй фразы типа "Подробнее по ссылке", "Читайте полную статью", "Больше информации в источнике" и т.п.
- НИКОГДА не пиши "В этой статье...", "Эта новость о...", "Данный материал..."
- НИКОГДА не добавляй рекламные элементы или призывы к действию
- НИКОГДА не используй вводные фразы типа "Как сообщается...", "По информации источника..."

СТРУКТУРА И СОДЕРЖАНИЕ:
- Начинай сразу с сути, без вступлений и предисловий
- Включай ВСЕ ключевые факты, цифры, даты, названия компаний, продуктов, технологий и имена важных лиц
- Если в статье есть инструкция - приведи ВСЕ шаги и важные детали
- Если в статье есть код - включи его полностью с необходимыми пояснениями
- Если в статье есть технические характеристики - перечисли их все
- Используй маркированные списки для перечисления функций, особенностей или шагов
- Структурируй информацию логически, разделяя на абзацы по смыслу
- Сохраняй все важные технические детали, не упрощай их
- Если в статье есть сравнения или таблицы - воспроизведи их в текстовом формате

СТИЛЬ:
- Пиши сухо, информативно, без "воды" и лишних слов
- Используй профессиональную терминологию там, где это уместно
- Добавляй в начало заголовка ОДИН подходящий эмодзи (смайлик), отражающий тематику новости
- НЕ используй эмодзи в тексте описания

ОБЪЕМ:
- Не ограничивай себя в объеме - лучше длинное и полное описание, чем короткое и неполное
- Если статья действительно очень большая, включи ВСЕ ключевые моменты и только в крайнем случае добавь в конце "[ССЫЛКА]"

Ответь в формате JSON со следующими полями:
- "approved": true/false - решение о публикации
- "reason": строка с объяснением решения
- "summary": подробное содержание статьи для публикации (если approved=true)
- "title": предлагаемый заголовок для публикации (если approved=true)
- "tags": массив выбранных тегов из списка доступных тегов (если approved=true)
"""

    try:
        # Отправляем запрос к нейросети
        completion = client.chat.completions.create(
            model="deepseek-r1-distill-llama-70b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1024,
            top_p=1,
            stream=False,
            stop=None,
        )
        
        # Получаем ответ
        response_text = completion.choices[0].message.content
        
        # Пытаемся извлечь JSON из ответа
        try:
            # Ищем JSON в ответе (может быть обернут в тройные кавычки или блок кода)
            import re
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```|```\s*([\s\S]*?)\s*```|(\{[\s\S]*\})', response_text)
            
            if json_match:
                json_str = next(filter(None, json_match.groups()))
                ai_response = json.loads(json_str)
            else:
                ai_response = json.loads(response_text)
                
            # Сохраняем статью в лог обработанных
            save_processed_article(article, ai_response)
            
            # Если статья одобрена, сохраняем её в лог одобренных
            if ai_response['approved']:
                # Проверяем наличие тегов и их формат
                if 'tags' not in ai_response or ai_response['tags'] is None:
                    ai_response['tags'] = []
                elif not isinstance(ai_response['tags'], list):
                    # Если теги не в виде списка, преобразуем их
                    if isinstance(ai_response['tags'], str):
                        ai_response['tags'] = [ai_response['tags']]
                    else:
                        ai_response['tags'] = []
                
                approved_article = {
                    'title': ai_response.get('title', article['title']),
                    'summary': ai_response['summary'],
                    'link': article['link'],
                    'source': article['source'],
                    'image_url': article.get('image_url'),
                    'tags': ai_response.get('tags', []),
                    'approved_at': datetime.now().isoformat()
                }
                save_approved_article(approved_article)
                
            return ai_response
            
        except json.JSONDecodeError as e:
            error_msg = f"Ошибка при разборе JSON из ответа нейросети для статьи '{article['title']}': {e}\nОтвет нейросети: {response_text}"
            logger.error(error_msg)
            send_error_to_telegram(error_msg)
            
            # Пытаемся извлечь данные из ответа с помощью регулярных выражений
            import re
            
            # Создаем словарь для хранения извлеченных данных
            extracted_data = {"error": "JSON parsing error", "raw_response": response_text}
            
            # Проверяем, есть ли в ответе "approved": true
            approved_match = re.search(r'"approved":\s*true', response_text)
            if approved_match:
                extracted_data["approved"] = True
                
                # Пытаемся извлечь summary
                summary_match = re.search(r'"summary":\s*"([^"]*(?:"[^"]*"[^"]*)*)"', response_text)
                if summary_match:
                    extracted_data["summary"] = summary_match.group(1).replace('\\"', '"')
                
                # Пытаемся извлечь title
                title_match = re.search(r'"title":\s*"([^"]*(?:"[^"]*"[^"]*)*)"', response_text)
                if title_match:
                    extracted_data["title"] = title_match.group(1).replace('\\"', '"')
                
                # Пытаемся извлечь reason
                reason_match = re.search(r'"reason":\s*"([^"]*(?:"[^"]*"[^"]*)*)"', response_text)
                if reason_match:
                    extracted_data["reason"] = reason_match.group(1).replace('\\"', '"')
                
                # Пытаемся извлечь теги
                tags_match = re.search(r'"tags":\s*(\[[^\]]*\])', response_text)
                if tags_match:
                    try:
                        extracted_data["tags"] = json.loads(tags_match.group(1))
                    except json.JSONDecodeError:
                        extracted_data["tags"] = []
                else:
                    extracted_data["tags"] = []
                
                # Сохраняем статью в лог обработанных с извлеченными данными
                save_processed_article(article, extracted_data)
                
                # Если удалось извлечь summary и title, сохраняем статью в лог одобренных
                if "summary" in extracted_data and "title" in extracted_data:
                    approved_article = {
                        'title': extracted_data.get('title', article['title']),
                        'summary': extracted_data['summary'],
                        'link': article['link'],
                        'source': article['source'],
                        'image_url': article.get('image_url'),
                        'tags': extracted_data.get('tags', []),
                        'approved_at': datetime.now().isoformat()
                    }
                    save_approved_article(approved_article)
                
                return extracted_data
            
            # Если не удалось извлечь данные, сохраняем статью в лог обработанных с ошибкой
            save_processed_article(article, extracted_data)
            return None
            
    except Exception as e:
        error_msg = f"Ошибка при обработке статьи '{article['title']}' нейросетью: {e}"
        logger.error(error_msg)
        send_error_to_telegram(error_msg)
        
        # Сохраняем статью в лог обработанных с ошибкой
        save_processed_article(article, {"error": str(e)})
        return None

def check_decenter_updates():
    """
    Проверяет обновления в канале DeCenter и обрабатывает новые статьи
    
    ВНИМАНИЕ: Эта функция устарела и больше не используется.
    Для добавления статей в общую очередь используйте класс DeCenterNewsSource
    в russian_news_sources.py
    
    Функция оставлена для обратной совместимости.
    """
    logger.info("Функция check_decenter_updates устарела. Используйте класс DeCenterNewsSource")
    
    # Получаем статьи из канала
    articles = parse_decenter_channel()
    
    logger.info(f"Получено {len(articles)} статей из канала DeCenter")
    logger.info("Статьи будут обработаны через общую очередь новостей")
    
    return 0  # Возвращаем 0, так как статьи не обрабатываются напрямую 