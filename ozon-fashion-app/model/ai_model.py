import os
import base64
from typing import List
from openai import OpenAI
from db import ClothingItem, get_db_session


# Инициализируем OpenAI клиент
try:
    from config import OPENAI_API_KEY
    client = OpenAI(api_key=OPENAI_API_KEY)
except ImportError:
    # Если config.py не найден, используем переменную окружения
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _encode_image_to_base64(image_path: str) -> str:
    """Кодирует изображение в base64 для отправки в OpenAI API."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def _analyze_image_with_openai(image_path: str, comment: str = "") -> dict:
    """
    Анализирует изображение одежды с помощью OpenAI Vision API.
    Возвращает словарь с описанием одежды.
    """
    try:
        # Кодируем изображение в base64
        base64_image = _encode_image_to_base64(image_path)
        
        # Формируем промпт для анализа
        prompt = f"""
        Проанализируй это изображение одежды и опиши его в формате JSON.
        
        Комментарий пользователя: "{comment}"
        
        Верни JSON с полями:
        - "type": тип одежды (например: "брюки", "платье", "блузка", "юбка")
        - "color": основной цвет
        - "style": стиль (например: "классический", "спортивный", "повседневный")
        - "keywords": массив ключевых слов для поиска
        
        Пример ответа:
        {{
            "type": "брюки",
            "color": "синий", 
            "style": "классический",
            "keywords": ["брюки", "синий", "классический", "деловой"]
        }}
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Используем более дешёвую модель
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=300
        )
        
        # Парсим ответ
        content = response.choices[0].message.content
        print(f"OpenAI ответ: {content}")  # Для отладки
        
        # Пытаемся извлечь JSON из ответа
        import json
        import re
        
        # Ищем JSON в ответе
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            # Если не удалось найти JSON, возвращаем базовый результат
            return {
                "type": "одежда",
                "color": "разноцветный",
                "style": "повседневный",
                "keywords": ["одежда"]
            }
            
    except Exception as e:
        print(f"Ошибка при анализе изображения: {e}")
        # Возвращаем базовый результат при ошибке
        return {
            "type": "одежда", 
            "color": "разноцветный",
            "style": "повседневный",
            "keywords": ["одежда"]
        }


def _search_items_by_analysis(analysis: dict, comment: str = "") -> List[ClothingItem]:
    """
    Ищет товары в базе данных на основе анализа изображения.
    """
    session = get_db_session()
    try:
        from sqlalchemy import or_, func
        
        # Собираем все ключевые слова для поиска
        search_keywords = analysis.get("keywords", [])
        
        # Добавляем слова из комментария
        if comment:
            search_keywords.extend(comment.lower().split())
        
        # Добавляем основные характеристики
        search_keywords.extend([
            analysis.get("type", ""),
            analysis.get("color", ""),
            analysis.get("style", "")
        ])
        
        # Убираем пустые строки и дубликаты
        search_keywords = list(set([kw.strip() for kw in search_keywords if kw.strip()]))
        
        print(f"Ключевые слова для поиска: {search_keywords}")  # Для отладки
        
        # Формируем запрос к базе данных
        query = session.query(ClothingItem)
        
        if search_keywords:
            # Создаём условия поиска по всем полям
            conditions = []
            for keyword in search_keywords:
                like_pattern = f"%{keyword}%"
                conditions.extend([
                    ClothingItem.name.ilike(like_pattern),
                    ClothingItem.description.ilike(like_pattern),
                    ClothingItem.category.ilike(like_pattern)
                ])
            
            # Объединяем условия через OR
            if conditions:
                query = query.filter(or_(*conditions))
        
        items = query.limit(20).all()  # Берём больше для лучшего выбора
        
        return items
        
    finally:
        session.close()


def find_similar_items(
    image_path: str,
    top_n: int = 5,
    comment: str = "",
) -> List[ClothingItem]:
    """
    Основная функция поиска похожих товаров с использованием OpenAI.
    
    1. Анализируем изображение с помощью OpenAI Vision API
    2. Ищем товары в базе данных по полученным характеристикам
    3. Возвращаем наиболее релевантные результаты
    """
    print(f"Начинаем анализ изображения: {image_path}")
    print(f"Комментарий пользователя: {comment}")
    
    # Анализируем изображение с помощью OpenAI
    analysis = _analyze_image_with_openai(image_path, comment)
    print(f"Результат анализа: {analysis}")
    
    # Ищем товары на основе анализа
    items = _search_items_by_analysis(analysis, comment)
    print(f"Найдено товаров: {len(items)}")
    
    # Возвращаем топ результатов
    return items[:top_n]
