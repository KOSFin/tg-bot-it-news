import time
import logging
import os
from bot import publish_next_from_queue

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Время ожидания между публикациями (в секундах)
PUBLICATION_DELAY = 10

def main():
    """
    Основная функция для публикации статей из очереди
    """
    logger.info("Запуск публикации статей из очереди")
    
    # Счетчик неудачных попыток публикации
    failed_publication_attempts = 0
    
    try:
        while True:
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
                    logger.info("Очередь на публикацию пуста. Ожидание...")
                    time.sleep(PUBLICATION_DELAY * 3)  # Увеличенная пауза, если очередь пуста
                    continue
                    
            except Exception as e:
                logger.error(f"Ошибка при публикации статьи: {e}")
                failed_publication_attempts += 1
            
            # Пауза между публикациями
            time.sleep(PUBLICATION_DELAY)
            
    except KeyboardInterrupt:
        logger.info("Программа остановлена пользователем")
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}")

if __name__ == "__main__":
    main() 