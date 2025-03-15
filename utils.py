import os
import json
from datetime import datetime

# Класс для сериализации объектов datetime в JSON
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def save_processed_news(news_items):
    """Сохранить обработанные новости в JSON файл"""
    if not os.path.exists('data'):
        os.makedirs('data')
        
    # Сохраняем в JSON для программной обработки
    json_filename = f"data/processed_news_{datetime.now().strftime('%Y%m%d')}.json"
    
    existing_data = []
    if os.path.exists(json_filename):
        with open(json_filename, 'r', encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []
    
    # Преобразуем datetime объекты в строки для JSON
    for item in news_items:
        if isinstance(item['published'], datetime):
            item['published'] = item['published'].isoformat()
    
    # Добавляем новые новости
    existing_links = [item['link'] for item in existing_data]
    new_items = []
    for item in news_items:
        if item['link'] not in existing_links:
            existing_data.append(item)
            new_items.append(item)
    
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)
    
    # Сохраняем в текстовый файл для удобного чтения
    if new_items:
        txt_filename = f"data/news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(txt_filename, 'w', encoding='utf-8') as f:
            f.write(f"Новости на {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")
            
            for item in new_items:
                f.write(f"[{item['source']}] {item['title']}\n")
                f.write(f"Ссылка: {item['link']}\n")
                f.write(f"Опубликовано: {item['published']}\n")
                f.write("-" * 50 + "\n\n")
        
        return txt_filename
    
    return None

def append_to_log_file(news_items):
    """Добавить новости в общий лог-файл"""
    if not news_items:
        return
        
    if not os.path.exists('data'):
        os.makedirs('data')
    
    log_filename = "data/all_news_log.txt"
    
    with open(log_filename, 'a', encoding='utf-8') as f:
        f.write(f"\n\n=== Новости на {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
        
        for item in news_items:
            pub_date = item['published']
            if isinstance(pub_date, str):
                try:
                    pub_date = datetime.fromisoformat(pub_date)
                except ValueError:
                    pub_date = "Неизвестно"
            
            f.write(f"[{item['source']}] {item['title']}\n")
            f.write(f"Ссылка: {item['link']}\n")
            f.write(f"Опубликовано: {pub_date}\n")
            f.write("-" * 50 + "\n\n") 

def save_news_to_json(news_items):
    """
    Сохраняет новости в JSON файл
    """
    # Создаем директорию, если не существует
    if not os.path.exists("data"):
        os.makedirs("data")
        
    json_filename = f"data/processed_news_{datetime.now().strftime('%Y%m%d')}.json"
    
    # Загружаем существующие данные, если файл существует
    existing_data = []
    if os.path.exists(json_filename):
        try:
            with open(json_filename, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except json.JSONDecodeError:
            existing_data = []
    
    # Преобразуем datetime объекты в строки для JSON
    for item in news_items:
        if isinstance(item['published'], datetime):
            item['published'] = item['published'].isoformat()
    
    # Добавляем новые данные
    existing_data.extend(news_items)
    
    # Сохраняем обновленные данные
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)
        
    return json_filename

def save_news_to_txt(news_items, filename=None):
    """
    Сохраняет новости в текстовый файл
    """
    # Создаем директорию, если не существует
    if not os.path.exists("data"):
        os.makedirs("data")
        
    txt_filename = filename or f"data/news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(txt_filename, 'w', encoding='utf-8') as f:
        f.write(f"Новости на {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 50 + "\n\n")
        
        for item in news_items:
            f.write(f"[{item['source']}] {item['title']}\n")
            f.write(f"Ссылка: {item['link']}\n")
            
            # Добавляем дату публикации, если она есть
            if 'published' in item:
                pub_date = item['published']
                if isinstance(pub_date, str):
                    try:
                        pub_date = datetime.fromisoformat(pub_date)
                        f.write(f"Дата: {pub_date.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    except:
                        f.write(f"Дата: {pub_date}\n")
                else:
                    f.write(f"Дата: {pub_date}\n")
            
            f.write("-" * 50 + "\n\n")
            
    return txt_filename

def append_to_txt(text, filename):
    """
    Добавляет текст в конец файла
    """
    with open(filename, 'a', encoding='utf-8') as f:
        f.write(f"\n\n=== Новости на {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
        f.write(text) 