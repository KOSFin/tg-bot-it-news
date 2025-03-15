import feedparser
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
import logging
import os
import re
import json
from ai_processor import parse_decenter_channel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RussianNewsSource:
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
            
    def _extract_article_content(self, url):
        """Извлекает содержимое статьи по URL"""
        try:
            response = requests.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Удаляем скрипты, стили и комментарии
            for script in soup(["script", "style"]):
                script.extract()
                
            # Пытаемся найти основной контент статьи
            # Это зависит от структуры сайта, поэтому используем несколько эвристик
            
            # Вариант 1: ищем div с классом, содержащим 'article', 'content', 'post'
            content_div = soup.find('div', class_=lambda c: c and any(x in c for x in ['article', 'content', 'post', 'entry']))
            
            # Вариант 2: ищем article тег
            if not content_div:
                content_div = soup.find('article')
                
            # Вариант 3: ищем main тег
            if not content_div:
                content_div = soup.find('main')
                
            # Если ничего не нашли, берем body
            if not content_div:
                content_div = soup.body
                
            if content_div:
                # Извлекаем текст
                text = content_div.get_text(separator=' ', strip=True)
                
                # Очищаем текст от лишних пробелов
                text = re.sub(r'\s+', ' ', text).strip()
                
                return text
            else:
                return "Не удалось извлечь содержимое статьи"
                
        except Exception as e:
            logger.error(f"Ошибка при извлечении содержимого статьи {url}: {e}")
            return "Ошибка при извлечении содержимого статьи"
            
    def _extract_image_url(self, url, soup=None):
        """Извлекает URL изображения-обложки статьи"""
        try:
            if not soup:
                response = requests.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
            
            # Пытаемся найти мета-тег с изображением
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                return og_image['content']
                
            # Ищем первое большое изображение в статье
            article_div = soup.find('article') or soup.find('div', class_=lambda c: c and any(x in c for x in ['article', 'content', 'post']))
            if article_div:
                img = article_div.find('img', class_=lambda c: c and any(x in c for x in ['featured', 'main', 'cover', 'header']))
                if not img:
                    img = article_div.find('img')
                if img and img.get('src'):
                    src = img['src']
                    if not src.startswith('http'):
                        # Преобразуем относительный URL в абсолютный
                        from urllib.parse import urljoin
                        src = urljoin(url, src)
                    return src
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении изображения из статьи {url}: {e}")
            return None


class RussianRSSNewsSource(RussianNewsSource):
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
                    # Извлекаем содержимое статьи
                    content = self._extract_article_content(entry.link)
                    
                    # Извлекаем URL изображения
                    image_url = None
                    if hasattr(entry, 'media_content') and entry.media_content:
                        for media in entry.media_content:
                            if 'url' in media:
                                image_url = media['url']
                                break
                    
                    if not image_url:
                        image_url = self._extract_image_url(entry.link)
                    
                    latest_news.append({
                        'title': entry.title,
                        'link': entry.link,
                        'published': pub_date,
                        'source': self.name,
                        'content': content,
                        'image_url': image_url
                    })
            
            return latest_news
        except Exception as e:
            logger.error(f"Ошибка при получении новостей из {self.name}: {e}")
            return []


class HabrNewsSource(RussianNewsSource):
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
                
                # Извлекаем содержимое статьи
                content = self._extract_article_content(link)
                
                # Извлекаем URL изображения
                image_url = self._extract_image_url(link)
                
                latest_news.append({
                    'title': title,
                    'link': link,
                    'published': pub_date,
                    'source': self.name,
                    'content': content,
                    'image_url': image_url
                })
            
            return latest_news
        except Exception as e:
            logger.error(f"Ошибка при получении новостей из Хабра: {e}")
            return []


class IXBTNewsSource(RussianNewsSource):
    def __init__(self):
        super().__init__("iXBT")
        self.url = "https://www.ixbt.com/news/"
        
    def get_latest_news(self):
        try:
            response = requests.get(self.url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Отладочная информация
            logger.info(f"Получен HTML от iXBT, размер: {len(response.text)} байт")
            
            # Находим все новости на странице
            news_items = soup.select('.item.no-padding')
            
            logger.info(f"Найдено {len(news_items)} новостей на iXBT")
            
            latest_news = []
            for item in news_items:
                # Получаем заголовок и ссылку
                title_element = item.select_one('h2 a')
                if not title_element:
                    continue
                    
                title = title_element.text.strip()
                link = title_element.get('href', '')
                if not link.startswith('http'):
                    link = "https://www.ixbt.com" + link
                
                # iXBT не предоставляет точное время в HTML, поэтому используем текущее время
                pub_date = datetime.now()
                
                # Извлекаем содержимое статьи
                content = self._extract_article_content(link)
                
                # Извлекаем URL изображения
                image_element = item.select_one('.image img')
                image_url = None
                if image_element and image_element.get('src'):
                    image_url = image_element['src']
                    if not image_url.startswith('http'):
                        image_url = "https://www.ixbt.com" + image_url
                
                if not image_url:
                    image_url = self._extract_image_url(link)
                
                latest_news.append({
                    'title': title,
                    'link': link,
                    'published': pub_date,
                    'source': self.name,
                    'content': content,
                    'image_url': image_url
                })
            
            return latest_news
        except Exception as e:
            logger.error(f"Ошибка при получении новостей из iXBT: {e}")
            return []


class DTFNewsSource(RussianNewsSource):
    def __init__(self):
        super().__init__("DTF")
        self.url = "https://dtf.ru/read/new"
        
    def get_latest_news(self):
        try:
            response = requests.get(self.url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Отладочная информация
            logger.info(f"Получен HTML от DTF, размер: {len(response.text)} байт")
            
            # Находим все статьи на странице
            articles = soup.select('.feed__item article')
            
            logger.info(f"Найдено {len(articles)} статей на DTF")
            
            latest_news = []
            for article in articles:
                # Получаем заголовок и ссылку
                title_element = article.select_one('.content-title')
                if not title_element:
                    continue
                    
                title = title_element.text.strip()
                
                # Получаем ссылку на статью
                link_element = article.select_one('a.content-link')
                if not link_element:
                    continue
                    
                link = link_element.get('href', '')
                
                # DTF не предоставляет точное время в HTML, поэтому используем текущее время
                pub_date = datetime.now()
                
                # Извлекаем содержимое статьи
                content = self._extract_article_content(link)
                
                # Извлекаем URL изображения
                image_element = article.select_one('.andropov_image img')
                image_url = None
                if image_element and image_element.get('src'):
                    image_url = image_element['src']
                
                if not image_url:
                    image_url = self._extract_image_url(link)
                
                latest_news.append({
                    'title': title,
                    'link': link,
                    'published': pub_date,
                    'source': self.name,
                    'content': content,
                    'image_url': image_url
                })
            
            return latest_news
        except Exception as e:
            logger.error(f"Ошибка при получении новостей из DTF: {e}")
            return []


class HabrNewsNewsSource(RussianNewsSource):
    def __init__(self):
        super().__init__("Новости Хабра")
        self.url = "https://habr.com/ru/news/"
        
    def get_latest_news(self):
        try:
            response = requests.get(self.url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Отладочная информация
            logger.info(f"Получен HTML от Новостей Хабра, размер: {len(response.text)} байт")
            
            # Пробуем разные селекторы, так как структура сайта может меняться
            articles = soup.select('article.tm-articles-list__item')
            if not articles:
                articles = soup.select('article.article-card')
            if not articles:
                articles = soup.select('article')
                
            logger.info(f"Найдено {len(articles)} новостей на Хабре")
            
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
                
                # Извлекаем содержимое статьи
                content = self._extract_article_content(link)
                
                # Извлекаем URL изображения
                image_url = self._extract_image_url(link)
                
                latest_news.append({
                    'title': title,
                    'link': link,
                    'published': pub_date,
                    'source': self.name,
                    'content': content,
                    'image_url': image_url
                })
            
            return latest_news
        except Exception as e:
            logger.error(f"Ошибка при получении новостей из Новостей Хабра: {e}")
            return []


class DeCenterNewsSource(RussianNewsSource):
    def __init__(self):
        super().__init__("DeCenter")
        
    def get_latest_news(self):
        try:
            logger.info(f"Получение новостей из Telegram канала DeCenter")
            
            # Используем функцию из ai_processor.py для парсинга канала
            articles = parse_decenter_channel()
            
            latest_news = []
            for article in articles:
                # Создаем объект новости, считая все статьи новыми
                news_item = {
                    'title': article['title'],
                    'content': article['content'],
                    'link': article['link'],
                    'published': datetime.now(),  # Используем текущее время
                    'source': self.name,
                    'image_url': article.get('image_url')
                }
                latest_news.append(news_item)
            
            if latest_news:
                logger.info(f"Получено {len(latest_news)} статей из Telegram канала DeCenter")
            return latest_news
            
        except Exception as e:
            logger.error(f"Ошибка при получении новостей из Telegram канала DeCenter: {e}")
            return []


# Создаем список источников новостей
def get_russian_news_sources():
    return [
        HabrNewsSource(),
        HabrNewsNewsSource(),
        DeCenterNewsSource()
    ] 