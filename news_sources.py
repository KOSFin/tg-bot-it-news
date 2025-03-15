import feedparser
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NewsSource:
    def __init__(self, name):
        self.name = name
        # Проверяем, был ли уже запуск скрипта
        if os.path.exists('data/last_check.txt'):
            with open('data/last_check.txt', 'r') as f:
                try:
                    last_check_str = f.read().strip()
                    self.last_check = datetime.fromisoformat(last_check_str)
                except:
                    # Если не удалось прочитать дату, считаем все статьи новыми
                    self.last_check = datetime.now() - timedelta(days=1)
        else:
            # При первом запуске считаем все статьи новыми
            self.last_check = datetime.now() - timedelta(days=1)
        
    def get_latest_news(self):
        """Получить последние новости из источника"""
        pass
        
    def _is_new_article(self, pub_date):
        """Проверить, является ли статья новой"""
        if pub_date > self.last_check:
            return True
        return False
        
    def update_last_check(self):
        """Обновить время последней проверки"""
        self.last_check = datetime.now()
        
        # Сохраняем время последней проверки в файл
        if not os.path.exists('data'):
            os.makedirs('data')
        with open('data/last_check.txt', 'w') as f:
            f.write(self.last_check.isoformat())


class RSSNewsSource(NewsSource):
    def __init__(self, name, rss_url):
        super().__init__(name)
        self.rss_url = rss_url
        
    def get_latest_news(self):
        try:
            feed = feedparser.parse(self.rss_url)
            latest_news = []
            
            for entry in feed.entries:
                # Преобразуем строку времени в объект datetime
                if hasattr(entry, 'published_parsed'):
                    pub_date = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed'):
                    pub_date = datetime(*entry.updated_parsed[:6])
                else:
                    # Если нет даты, считаем статью новой
                    pub_date = datetime.now()
                
                if self._is_new_article(pub_date):
                    latest_news.append({
                        'title': entry.title,
                        'link': entry.link,
                        'published': pub_date,
                        'source': self.name
                    })
            
            return latest_news
        except Exception as e:
            logger.error(f"Ошибка при получении новостей из {self.name}: {e}")
            return []


class HabrNewsSource(NewsSource):
    def __init__(self):
        super().__init__("Хабр")
        self.url = "https://habr.com/ru/all/"
        
    def get_latest_news(self):
        try:
            response = requests.get(self.url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Отладочная информация
            logger.info(f"Получен HTML от Хабра, размер: {len(response.text)} байт")
            
            # Пробуем разные селекторы, так как структура сайта может меняться
            articles = soup.select('article.tm-articles-list__item')
            if not articles:
                articles = soup.select('article.article-card')
            if not articles:
                articles = soup.select('article')
                
            logger.info(f"Найдено {len(articles)} статей на Хабре")
            
            latest_news = []
            for article in articles:
                # Пробуем разные селекторы для заголовка
                title_element = article.select_one('.tm-article-snippet__title-link')
                if not title_element:
                    title_element = article.select_one('.article-card__title a')
                if not title_element:
                    title_element = article.select_one('h2 a')
                
                if not title_element:
                    continue
                    
                title = title_element.text.strip()
                
                # Пробуем получить ссылку
                link = title_element.get('href', '')
                if not link.startswith('http'):
                    link = "https://habr.com" + link
                
                # Хабр не предоставляет точное время в HTML, поэтому используем текущее время
                pub_date = datetime.now()
                
                latest_news.append({
                    'title': title,
                    'link': link,
                    'published': pub_date,
                    'source': self.name
                })
            
            return latest_news
        except Exception as e:
            logger.error(f"Ошибка при получении новостей из Хабра: {e}")
            return []


# Создаем список источников новостей
def get_news_sources():
    return [
        RSSNewsSource("TechCrunch", "https://techcrunch.com/feed/"),
        RSSNewsSource("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
        RSSNewsSource("The Verge", "https://www.theverge.com/rss/index.xml"),
        RSSNewsSource("Wired", "https://www.wired.com/feed/rss"),
        RSSNewsSource("GitHub Blog", "https://github.blog/feed/"),
        HabrNewsSource()
    ] 