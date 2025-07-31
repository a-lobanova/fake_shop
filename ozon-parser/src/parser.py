import time
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from db import save_clothing_item
from models.clothing_item import ClothingItem


def fetch_html(url, min_items=100):
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    )

    driver = uc.Chrome(options=options)
    driver.get(url)

    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, '[data-widget="searchResultsV2"]')
            )
        )
        last_count = 0
        for _ in range(50):  # максимум 30 скроллов
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            # Проверяем, сколько товаров загружено
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            items = soup.select("div.tile-root")
            if len(items) >= min_items:
                break
            # Если больше не грузится — выходим
            if len(items) == last_count:
                break
            last_count = len(items)
    except Exception as e:
        print("Timeout or error while loading page:", e)

    html = driver.page_source
    driver.quit()
    return html


import base64
import requests


def download_image_as_base64(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return base64.b64encode(response.content).decode("utf-8")
    except Exception as e:
        print(f"Ошибка загрузки изображения: {e}")
        return ""


def parse_clothing_items(html):
    soup = BeautifulSoup(html, "html.parser")
    # Парсим категорию
    category_tag = soup.select_one("h1.qb61_3_0-a1")
    category = category_tag.text.strip() if category_tag else ""

    items = []
    for item in soup.select("div.tile-root"):
        name_tag = item.select_one("span.tsBody500Medium")
        price_tag = item.select_one("span.tsHeadline500Medium")
        link_tag = item.select_one("a.tile-clickable-element")
        img_tag = item.select_one("img")

        if not price_tag:
            price_tag = item.select_one("span.c35_3_1-a1.tsHeadline500Medium")

        if name_tag and price_tag and link_tag and img_tag:
            name = name_tag.text.strip()
            price_str = (
                price_tag.text.strip()
                .replace("\u2009", "")
                .replace("₽", "")
                .replace(" ", "")
            )
            try:
                price = float(price_str)
            except ValueError:
                print(f"Ошибка конвертации цены: {price_str}")
                continue

            url = "https://www.ozon.ru" + link_tag.get("href", "")
            image_url = img_tag.get("src", "")
            image_blob = download_image_as_base64(image_url)
            clothing_item = ClothingItem(name, price, "", url, image_url)
            # Добавляем вручную новые поля
            clothing_item.image_blob = image_blob
            clothing_item.category = category
            items.append(clothing_item)
    return items


def main():
    links = [
        "https://www.ozon.ru/category/bryuki-zhenskie-7512/",
        "https://www.ozon.ru/category/zhenskie-bluzy-i-rubashki-7511/",
        "https://www.ozon.ru/category/zhakety-i-zhilety-zhenskie-7535/",
        "https://www.ozon.ru/category/futbolki-i-topy-zhenskie-7505/",
        "https://www.ozon.ru/category/yubki-zhenskie-7504/",
    ]
    total = 0
    for url in links:
        print(f"Парсим: {url}")
        html = fetch_html(url, min_items=100)
        if "Доступ ограничен" in html:
            print("Доступ ограничен! Пропускаем ссылку.")
            continue
        clothing_items = parse_clothing_items(html)
        print(f"Найдено {len(clothing_items)} товаров.")
        total += len(clothing_items)
        for item in clothing_items:
            print(
                f"Name: {item.name}, Price: {item.price}, URL: {item.url}, Image: {item.image_url}, Category: {item.category}"
            )
            save_clothing_item(
                item.name,
                item.price,
                " ",
                item.url,
                item.image_url,
                item.image_blob,
                item.category,
            )
    print(f"Всего сохранено: {total} товаров.")


if __name__ == "__main__":
    main()
