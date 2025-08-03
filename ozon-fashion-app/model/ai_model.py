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
        return base64.b64encode(image_file.read()).decode("utf-8")


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
            Ты — AI-стилист. Пользователь прикрепил изображение одежды и просит подобрать вещь к этому образу.

            Проанализируй изображение и комментарий пользователя: "{comment}"

            Верни JSON с полями:
            - "query_category": категория одежды, которую нужно подобрать. Выбери ТОЛЬКО из:
                "Брюки, бриджи и капри женские",
                "Блузы и рубашки женские",
                "Пиджаки, жакеты и жилеты женские",
                "Футболки и топы женские",
                "Юбки женские"
            - "target_description": краткое описание вещи на изображении (тип, цвет, стиль)
            - "keywords": массив ключевых слов, включающий **только `query_category` как текст** и, при необходимости, дополнительные слова для поиска по `name`.

            Пример:
            {{
                "query_category": "Пиджаки, жакеты и жилеты женские",
                "target_description": "Белая футболка, повседневный стиль",
                "keywords": ["Пиджаки, жакеты и жилеты женские", "пиджак", "повседневный", "женский"]
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
                            },
                        },
                    ],
                }
            ],
            max_tokens=300,
        )

        # Парсим ответ
        content = response.choices[0].message.content
        print(f"OpenAI ответ: {content}")  # Для отладки

        # Пытаемся извлечь JSON из ответа
        import json
        import re

        # Ищем JSON в ответе
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            # Если не удалось найти JSON, возвращаем базовый результат
            return {
                "type": "одежда",
                "color": "разноцветный",
                "style": "повседневный",
                "keywords": ["одежда"],
            }

    except Exception as e:
        print(f"Ошибка при анализе изображения: {e}")
        # Возвращаем базовый результат при ошибке
        return {
            "type": "одежда",
            "color": "разноцветный",
            "style": "повседневный",
            "keywords": ["одежда"],
        }


def _search_items_by_analysis(analysis: dict, comment: str = "") -> List[ClothingItem]:
    """
    Ищет товары в базе данных на основе анализа изображения и комментария пользователя.
    """
    session = get_db_session()
    try:
        from sqlalchemy import or_

        # Извлекаем query_category
        query_category = analysis.get("query_category", "").strip()

        # Собираем ключевые слова
        search_keywords = analysis.get("keywords", [])

        # Добавляем слова из комментария
        if comment:
            search_keywords.extend(comment.lower().split())

        # Добавляем основные характеристики (если они есть)
        search_keywords.extend(
            [
                analysis.get("type", ""),
                analysis.get("color", ""),
                analysis.get("style", ""),
            ]
        )

        # Убираем пустые строки и дубликаты
        search_keywords = list(set(kw.strip() for kw in search_keywords if kw.strip()))

        print(f"Категория поиска: {query_category}")
        print(f"Ключевые слова для поиска: {search_keywords}")

        # Шаг 1: фильтрация по категории
        query = session.query(ClothingItem)
        if query_category:
            query = query.filter(ClothingItem.category.ilike(f"%{query_category}%"))

        # Шаг 2: попытка фильтрации по ключевым словам
        items = []
        if search_keywords:
            keyword_conditions = []
            for keyword in search_keywords:
                like_pattern = f"%{keyword}%"
                keyword_conditions.extend(
                    [
                        ClothingItem.name.ilike(like_pattern),
                        ClothingItem.description.ilike(like_pattern),
                    ]
                )
            # Пробуем применить фильтр по ключевым словам
            items = query.filter(or_(*keyword_conditions)).limit(20).all()

        # Шаг 3: если найдено мало результатов — возвращаем только по категории
        if len(items) < 5:
            items = query.limit(20).all()

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
