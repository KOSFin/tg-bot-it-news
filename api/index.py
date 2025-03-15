from http.server import BaseHTTPRequestHandler
import json
import os
import sys

# Добавляем корневую директорию проекта в sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Импортируем необходимые модули из основного проекта
from bot import send_message_to_channel
from ai_processor import process_article
from utils import load_json_file, save_json_file

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response = {
            "status": "ok",
            "message": "IT News Bot API is running"
        }
        
        self.wfile.write(json.dumps(response).encode())
        return
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode())
            
            # Обработка различных типов запросов
            if self.path == '/api/process':
                # Обработка новой статьи
                if 'article' in data:
                    result = process_article(data['article'])
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(result).encode())
                    return
            
            elif self.path == '/api/publish':
                # Публикация статьи в канал
                if 'article_id' in data:
                    # Здесь должна быть логика публикации
                    # Для примера просто возвращаем успех
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "published"}).encode())
                    return
            
            # Если путь не распознан
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Unknown endpoint"}).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode()) 