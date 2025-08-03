import os
import sys
import base64
import requests
import io
from typing import List, Dict, Tuple
from openai import OpenAI
from PIL import Image

# Добавляем путь к нашему проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
    try:
        # Открываем изображение через PIL для поддержки всех форматов
        with Image.open(image_path) as img:
            # Конвертируем в RGB (убираем альфа-канал если есть)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Сохраняем в буфер как JPEG
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"⚠️  Ошибка обработки изображения {image_path}: {e}")
        # Fallback: попробуем прочитать как есть
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')


def _download_and_encode_image(url: str) -> str:
    """Скачивает изображение по URL и кодирует в base64."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Получаем размер изображения
        content_length = len(response.content)
        print(f"         📊 Размер: {content_length} байт")
        
        img = Image.open(io.BytesIO(response.content)).convert("RGB")
        print(f"         🖼️  Разрешение: {img.size[0]}x{img.size[1]}")
        
        # Конвертируем в base64
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        base64_size = len(buffer.getvalue())
        print(f"         📦 Base64: {base64_size} байт")
        
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"         ❌ Ошибка загрузки: {e}")
        return None


def _agent_1_process_request(comment: str, image_path: str = None) -> dict:
    """
    АГЕНТ 1: Обрабатывает пользовательский запрос и формирует поисковый запрос в БД.
    
    Анализирует текст пользователя и опционально изображение для определения:
    - Какие категории товаров искать
    - Какие ключевые слова использовать
    - Тип поиска (конкретный товар или комплементарные)
    """
    print("🤖 АГЕНТ 1: Обрабатываю запрос пользователя...")
    
    try:
        # Анализируем запрос с помощью OpenAI
        prompt = f"""
        Анализируй запрос пользователя для поиска женской одежды: "{comment}"
        
        Доступные категории:
        - "Брюки, бриджи и капри женские"
        - "Блузы и рубашки женские" 
        - "Пиджаки, жакеты и жилеты женские"
        - "Футболки и топы женские"
        - "Юбки женские"
        
        Правила:
        - Если запрос содержит конкретный тип одежды (футболка, брюки, юбка) → search_type: "specific"
        - Если запрос общий ("что подойдёт", "дополни образ") → search_type: "complementary"
        
        Примеры:
        "Подбери футболку" → specific, categories: ["Футболки и топы женские"]
        "Что подойдёт к этому образу?" → complementary, categories: [все категории]
        
        Ответ СТРОГО в JSON:
        {{
            "categories": ["точные названия категорий"],
            "keywords": ["ключевые слова"],
            "search_type": "specific или complementary",
            "reasoning": "объяснение"
        }}"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.1  # Снижаем температуру для более стабильного JSON
        )
        
        import json
        import re
        
        # Получаем ответ и очищаем от лишних символов
        raw_response = response.choices[0].message.content.strip()
        print(f"🔍 АГЕНТ 1: Сырой ответ: {raw_response}")
        
        # Пытаемся извлечь JSON из ответа
        json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            result = json.loads(json_str)
        else:
            raise ValueError("JSON не найден в ответе")
        
        print(f"🧠 АГЕНТ 1 определил:")
        print(f"   📂 Категории: {result['categories']}")
        print(f"   🔤 Ключевые слова: {result['keywords']}")
        print(f"   🎯 Тип поиска: {result['search_type']}")
        print(f"   💭 Логика: {result['reasoning']}")
        
        return {
            "requested_categories": result["categories"],
            "search_keywords": result["keywords"],
            "search_type": result["search_type"],
            "reasoning": result["reasoning"],
            "original_comment": comment
        }
        
    except Exception as e:
        print(f"⚠️  АГЕНТ 1: Ошибка AI анализа, использую fallback: {e}")
        
        # Fallback: улучшенный парсинг
        comment_lower = comment.lower()
        
        category_keywords = {
            "Брюки, бриджи и капри женские": ["брюки", "джинсы", "штаны", "легинсы", "капри", "бриджи"],
            "Блузы и рубашки женские": ["блузка", "рубашка", "блуза", "сорочка"],
            "Пиджаки, жакеты и жилеты женские": ["пиджак", "жакет", "жилет", "кардиган", "блейзер"],
            "Футболки и топы женские": ["футболка", "футболку", "топ", "майка", "тишка"],
            "Юбки женские": ["юбка", "юбку", "мини", "макси"]
        }
        
        mentioned_categories = []
        for category, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in comment_lower:
                    mentioned_categories.append(category)
                    break
        
        # Улучшенная логика определения типа поиска
        if mentioned_categories:
            search_type = "specific"
            print(f"🎯 Fallback: Найдены конкретные категории: {mentioned_categories}")
        else:
            mentioned_categories = list(category_keywords.keys())
            search_type = "complementary"
            print(f"🔄 Fallback: Комплементарный поиск по всем категориям")
        
        return {
            "requested_categories": mentioned_categories,
            "search_keywords": comment_lower.split(),
            "search_type": search_type,
            "reasoning": "Fallback анализ по ключевым словам",
            "original_comment": comment
        }


def _agent_2_validate_items(original_image_path: str, candidate_items: List[ClothingItem], user_comment: str, search_info: dict) -> List[ClothingItem]:
    """
    АГЕНТ 2: Валидирует найденные товары по фото и выбирает наиболее подходящие.
    
    Использует OpenAI Vision для анализа исходного фото пользователя и сравнения
    с товарами из БД, выбирая лучшие варианты по стилю и сочетаемости.
    """
    print(f"🤖 АГЕНТ 2: Валидирую товары по фото...")
    print(f"   🎯 Тип поиска: {search_info.get('search_type')}")
    print(f"   💭 Логика поиска: {search_info.get('reasoning')}")
    
    try:
        # Кодируем исходное изображение
        original_base64 = _encode_image_to_base64(original_image_path)
        
        # Группируем товары по категориям
        categories = {}
        for item in candidate_items:
            category = item.category
            if category not in categories:
                categories[category] = []
            categories[category].append(item)
        
        print(f"📦 Найдено товаров в {len(categories)} категориях")
        
        best_items = []
        
        for category, items in categories.items():
            print(f"🔍 Валидирую категорию: {category} ({len(items)} товаров)")
            
            if len(items) == 1:
                # Если товар один, берём его
                print(f"   ✅ Единственный товар: {items[0].name[:40]}... ({items[0].price}₽)")
                best_items.append(items[0])
                continue
            
            # Умный выбор количества товаров для сравнения
            max_items_to_compare = min(5, len(items))  # До 5 товаров максимум
            
            # Если товаров много, берём разнообразную выборку
            if len(items) > max_items_to_compare:
                # Берём первые (самые релевантные) + случайные из середины и конца
                items_to_compare = items[:2]  # Первые 2 самых релевантных
                if len(items) > 10:
                    # Добавляем товары из середины и конца для разнообразия
                    mid_idx = len(items) // 2
                    items_to_compare.extend([items[mid_idx], items[-2], items[-1]])
                else:
                    # Если товаров не очень много, берём равномерно
                    step = len(items) // max_items_to_compare
                    for i in range(2, max_items_to_compare):
                        idx = min(i * step, len(items) - 1)
                        items_to_compare.append(items[idx])
                
                # Убираем дубликаты и ограничиваем
                seen = set()
                unique_items = []
                for item in items_to_compare:
                    if item.id not in seen:
                        seen.add(item.id)
                        unique_items.append(item)
                items_to_compare = unique_items[:max_items_to_compare]
            else:
                items_to_compare = items[:max_items_to_compare]
            
            print(f"   📊 Стратегия выбора: {len(items)} товаров → {len(items_to_compare)} для AI анализа")
            print(f"   📋 Кандидаты для сравнения:")
            for i, item in enumerate(items_to_compare, 1):
                print(f"      {i}. {item.name[:35]}... ({item.price}₽)")
                print(f"         🖼️  Изображение: {item.image_url[:50] if item.image_url else 'Нет'}...")
            
            # Собираем изображения товаров
            candidate_images = []
            valid_items = []
            
            print(f"   🔄 Загружаю изображения товаров...")
            for i, item in enumerate(items_to_compare, 1):
                if item.image_url:
                    print(f"      📥 Загружаю изображение {i}: {item.image_url[:60]}...")
                    item_base64 = _download_and_encode_image(item.image_url)
                    if item_base64:
                        candidate_images.append(item_base64)
                        valid_items.append(item)
                        print(f"      ✅ Изображение {i} загружено успешно")
                    else:
                        print(f"      ❌ Ошибка загрузки изображения {i}")
                else:
                    print(f"      ⚠️  У товара {i} нет изображения")
            
            if not candidate_images:
                # Если нет изображений, берём первый товар
                print(f"      ⚠️  Нет доступных изображений, выбираю первый товар")
                print(f"      ✅ Выбран: {items[0].name[:40]}... ({items[0].price}₽)")
                best_items.append(items[0])
                continue
            
            print(f"   🎯 Готов к AI анализу: {len(candidate_images)} изображений")
            
            # Адаптивный промпт в зависимости от типа поиска
            search_type = search_info.get('search_type', 'specific')
            
            # Динамический промпт в зависимости от количества товаров
            num_items = len(valid_items)
            items_list = []
            valid_numbers = []
            
            for i, item in enumerate(valid_items, 1):
                items_list.append(f"ИЗОБРАЖЕНИЕ {i+1}: Товар №{i} - {item.name[:40]}")
                valid_numbers.append(str(i))
            
            items_description = "\n                ".join(items_list)
            valid_range = ", ".join(valid_numbers)
            
            if search_type == 'specific':
                prompt = f"""
                Пользователь ищет конкретный тип одежды: "{user_comment}"
                
                ИЗОБРАЖЕНИЕ 1: Исходное фото пользователя (НЕ для выбора)
                {items_description}
                
                Выбери НОМЕР ТОВАРА ({valid_range}), который лучше всего соответствует запросу.
                Учитывай стиль, цвет, фасон и качество товара.
                
                ВАЖНО: Отвечай только цифрой товара: {valid_range}
                """
            else:
                prompt = f"""
                Пользователь ищет дополняющие товары к своему образу: "{user_comment}"
                
                ИЗОБРАЖЕНИЕ 1: Исходный образ пользователя (НЕ для выбора)
                {items_description}
                
                Выбери НОМЕР ТОВАРА ({valid_range}), который лучше всего дополнит исходный образ.
                Учитывай сочетаемость по стилю, цветам и общую гармонию образа.
                
                ВАЖНО: Отвечай только цифрой товара: {valid_range}
                """
            
            # Формируем сообщения с изображениями
            content = [{"type": "text", "text": prompt}]
            
            # Добавляем исходное изображение
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{original_base64}"}
            })
            
            # Добавляем изображения кандидатов
            for img_base64 in candidate_images:
                content.append({
                    "type": "image_url", 
                    "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}
                })
            
            # Отправляем запрос в OpenAI
            print(f"   🧠 Отправляю запрос в OpenAI Vision...")
            print(f"      📤 Модель: gpt-4o-mini")
            print(f"      📤 Изображений: {len(content) - 1} (включая исходное)")
            print(f"      📤 Тип поиска: {search_type}")
            print(f"   📋 Структура изображений для AI:")
            print(f"      🖼️  1. Исходное фото пользователя (НЕ для выбора)")
            for i, item in enumerate(valid_items, 1):
                print(f"      🖼️  {i+1}. Товар №{i}: {item.name[:35]}...")
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": content}],
                max_tokens=5
            )
            
            # Парсим ответ
            choice = response.choices[0].message.content.strip()
            print(f"   🤖 AI ответил: '{choice}'")
            
            # Показываем соответствие выбора товарам
            valid_range = ", ".join([str(i) for i in range(1, len(valid_items) + 1)])
            print(f"   🔍 Расшифровка выбора AI:")
            print(f"      AI ответил: '{choice}' (должно быть {valid_range})")
            for i, item in enumerate(valid_items, 1):
                marker = "👉" if choice == str(i) else "  "
                print(f"      {marker} Товар №{i}: {item.name[:30]}... ({item.price}₽)")
            
            try:
                choice_num = int(choice)
                
                # Если AI ответил номером изображения (2, 3, 4, 5, 6), конвертируем в номер товара (1, 2, 3, 4, 5)
                if choice_num >= 2 and choice_num <= len(valid_items) + 1:
                    choice_idx = choice_num - 2  # 2->0, 3->1, 4->2, 5->3, 6->4
                    print(f"   🔄 Конвертирую номер изображения {choice_num} в номер товара {choice_idx + 1}")
                # Если AI ответил номером товара (1, 2, 3, 4, 5)
                elif choice_num >= 1 and choice_num <= len(valid_items):
                    choice_idx = choice_num - 1  # 1->0, 2->1, 3->2, 4->3, 5->4
                    print(f"   ✅ Использую номер товара {choice_num} как есть")
                else:
                    choice_idx = -1  # Некорректный выбор
                
                if 0 <= choice_idx < len(valid_items):
                    selected_item = valid_items[choice_idx]
                    best_items.append(selected_item)
                    print(f"   ✅ ВЫБРАН: {selected_item.name[:40]}... ({selected_item.price}₽)")
                else:
                    fallback_item = valid_items[0]
                    best_items.append(fallback_item)
                    print(f"   ⚠️  Некорректный выбор '{choice}', взят первый товар")
                    print(f"   ✅ ВЫБРАН: {fallback_item.name[:40]}... ({fallback_item.price}₽)")
            except (ValueError, IndexError):
                fallback_item = valid_items[0]
                best_items.append(fallback_item)
                print(f"   ❌ Ошибка парсинга выбора '{choice}', взят первый товар")
                print(f"   ✅ ВЫБРАН: {fallback_item.name[:40]}... ({fallback_item.price}₽)")
        
        print(f"🎯 АГЕНТ 2: Итоговый результат - {len(best_items)} товаров:")
        for i, item in enumerate(best_items, 1):
            print(f"   {i}. {item.name[:45]}... ({item.price}₽)")
            print(f"      📂 Категория: {item.category}")
        
        return best_items
        
    except Exception as e:
        print(f"❌ Ошибка при валидации: {e}")
        # Fallback: по одному товару из каждой категории
        categories = {}
        for item in candidate_items:
            category = item.category
            if category not in categories:
                categories[category] = item
        return list(categories.values())


def _search_items_by_request(request_info: dict) -> List[ClothingItem]:
    """
    Ищет товары в базе данных по запросу пользователя.
    Простой и быстрый поиск без детального анализа изображения.
    """
    session = get_db_session()
    try:
        from sqlalchemy import or_
        
        categories = request_info.get("requested_categories", [])
        keywords = request_info.get("search_keywords", [])
        
        print(f"🎯 Ищу товары в категориях: {categories}")
        print(f"🔤 Ключевые слова: {keywords}")
        
        # Формируем запрос к базе данных
        query = session.query(ClothingItem)
        
        # Стратегия поиска: приоритет категориям над ключевыми словами
        all_conditions = []
        
        search_type = request_info.get("search_type", "specific")
        
        # Определяем стратегию поиска на основе типа
        if search_type == "specific":  # Конкретный запрос
            print(f"🎯 Точечный поиск по категориям: {categories}")
            category_conditions = []
            for category in categories:
                category_conditions.append(ClothingItem.category.ilike(f"%{category}%"))
            
            # Для конкретного запроса используем только категории
            all_conditions = category_conditions
            
        else:  # Комплементарный поиск
            print(f"🔍 Комплементарный поиск по категориям: {categories}")
            # Добавляем условия по категориям
            if categories:
                for category in categories:
                    all_conditions.append(ClothingItem.category.ilike(f"%{category}%"))
            
            # Добавляем условия по ключевым словам
            relevant_keywords = [kw for kw in keywords if len(kw) > 2 and kw not in ['подбери', 'найди', 'покажи']]
            if relevant_keywords:
                print(f"🔍 Добавляю поиск по ключевым словам: {relevant_keywords}")
                for keyword in relevant_keywords:
                    like_pattern = f"%{keyword}%"
                    all_conditions.extend([
                        ClothingItem.name.ilike(like_pattern),
                        ClothingItem.description.ilike(like_pattern),
                        ClothingItem.category.ilike(like_pattern)
                    ])
        
        # Применяем все условия через OR
        if all_conditions:
            print(f"🔍 Всего условий поиска: {len(all_conditions)}")
            query = query.filter(or_(*all_conditions))
        else:
            print("⚠️  Нет условий для поиска, возвращаю все товары")
        
        # Ограничиваем результат
        items = query.limit(30).all()
        
        print(f"📦 Найдено {len(items)} товаров по запросу")
        
        # Fallback: если ничего не найдено, но есть категории, ищем только по категориям
        if not items and categories:
            print("🔄 Fallback: ищу только по категориям")
            fallback_query = session.query(ClothingItem)
            category_conditions = []
            for category in categories:
                print(f"🔍 Fallback ищет категорию: '{category}'")
                category_conditions.append(ClothingItem.category.ilike(f"%{category}%"))
            
            if category_conditions:
                fallback_query = fallback_query.filter(or_(*category_conditions))
                
                # Отладка: показываем SQL запрос
                print(f"🔍 SQL запрос: {fallback_query}")
                
                items = fallback_query.limit(30).all()
                print(f"📦 Fallback нашёл {len(items)} товаров")
                
                # Если всё ещё 0, попробуем совсем простой запрос
                if not items:
                    print("🔍 Пробую самый простой запрос...")
                    simple_query = session.query(ClothingItem).filter(
                        ClothingItem.category.ilike("%Пиджаки%")
                    )
                    simple_items = simple_query.limit(5).all()
                    print(f"📦 Простой запрос нашёл {len(simple_items)} товаров")
                    
                    # Проверяем общее количество товаров в базе
                    total_count = session.query(ClothingItem).count()
                    print(f"📊 Всего товаров в базе: {total_count}")
                    
                    # Проверяем первые 3 товара
                    first_items = session.query(ClothingItem).limit(3).all()
                    print(f"📋 Первые товары в базе:")
                    for i, item in enumerate(first_items, 1):
                        print(f"   {i}. {item.name} | Категория: '{item.category}'")
                    
                    if simple_items:
                        items = simple_items
        
        return items
        
    finally:
        session.close()


def find_similar_items(
    image_path: str,
    top_n: int = 5,
    comment: str = "",
) -> List[ClothingItem]:
    """
    Двухэтапная система подбора товаров с двумя AI агентами:
    
    АГЕНТ 1: Анализирует запрос пользователя и формирует поисковый запрос в БД
    АГЕНТ 2: Валидирует найденные товары по фото и выбирает лучшие
    """
    print(f"🛍️  Двухэтапный AI поиск товаров начался...")
    print(f"📸 Фото: {image_path}")
    print(f"💭 Запрос: '{comment}'")
    print("=" * 50)
    
    # ЭТАП 1: АГЕНТ 1 обрабатывает запрос пользователя
    print("🔥 ЭТАП 1: Анализ запроса пользователя")
    search_info = _agent_1_process_request(comment, image_path)
    print(f"📋 Определил категории: {search_info['requested_categories']}")
    print(f"🎯 Тип поиска: {search_info['search_type']}")
    
    # Поиск в базе данных на основе результатов АГЕНТА 1
    candidate_items = _search_items_by_request(search_info)
    
    if not candidate_items:
        print("😞 Товары не найдены")
        return []
    
    print(f"📦 Найдено кандидатов: {len(candidate_items)}")
    print("=" * 50)
    
    # ЭТАП 2: АГЕНТ 2 валидирует товары по фото
    print("🔥 ЭТАП 2: AI валидация по фото")
    try:
        best_items = _agent_2_validate_items(image_path, candidate_items, comment, search_info)
    except Exception as e:
        print(f"⚠️  АГЕНТ 2: Ошибка валидации: {e}")
        # Fallback: по одному товару из каждой категории
        categories = {}
        for item in candidate_items:
            category = item.category
            if category not in categories:
                categories[category] = item
        best_items = list(categories.values())
    
    # Ограничиваем результат
    final_items = best_items[:top_n]
    
    print("=" * 50)
    print(f"✨ ФИНАЛЬНЫЙ РЕЗУЛЬТАТ: {len(final_items)} товаров")
    for i, item in enumerate(final_items, 1):
        print(f"   {i}. {item.name[:35]}... ({item.price}₽)")
        print(f"      {item.category}")
    
    return final_items
