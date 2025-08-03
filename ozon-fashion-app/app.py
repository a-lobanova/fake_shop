from flask import Flask, render_template, request, redirect, url_for, session
import os
from db import find_similar_items, get_item_by_id
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = "your_secret_key"
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Отладка: проверяем настройки статических файлов
print(f"📁 Static folder: {app.static_folder}")
print(f"📁 Static URL path: {app.static_url_path}")
print(f"📁 Upload folder: {UPLOAD_FOLDER}")
print(f"📁 Upload folder exists: {os.path.exists(UPLOAD_FOLDER)}")


@app.route("/", methods=["GET", "POST"])
def index():
    user_photo = None
    items = None
    comment = ""
    if request.method == "POST":
        file = request.files["photo"]
        comment = request.form.get("comment", "")
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            # Убеждаемся, что файл сохранён правильно
            os.chmod(filepath, 0o644)  # Устанавливаем права доступа
            
            user_photo = filepath.replace("\\", "/")  # Для корректного отображения в HTML
            
            # Отладочная информация
            print(f"📁 Загружен файл: {filename}")
            print(f"📁 Полный путь: {filepath}")
            print(f"📁 Путь для HTML: {user_photo}")
            print(f"📁 Файл существует: {os.path.exists(filepath)}")
            if os.path.exists(filepath):
                print(f"📁 Размер файла: {os.path.getsize(filepath)} байт")
            
            items = find_similar_items(filepath, comment=comment)
            print("items:", items)  # <-- print для отладки
            return render_template(
                "index.html", user_photo=user_photo, items=items, comment=comment
            )
    # GET-запрос
    return render_template(
        "index.html", user_photo=user_photo, items=items, comment=comment
    )


@app.route("/add_to_cart/<int:item_id>")
def add_to_cart(item_id):
    cart = session.get("cart", [])
    cart.append(item_id)
    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/cart")
def cart():
    cart = session.get("cart", [])
    items = [get_item_by_id(i) for i in cart]
    return render_template("cart.html", items=items)


@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    """Обслуживание загруженных файлов"""
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    abs_file_path = os.path.abspath(file_path)  # Получаем абсолютный путь
    
    print(f"🔍 Запрос файла: {filename}")
    print(f"🔍 Относительный путь: {file_path}")
    print(f"🔍 Абсолютный путь: {abs_file_path}")
    print(f"🔍 Файл существует: {os.path.exists(abs_file_path)}")
    
    if os.path.exists(abs_file_path):
        from flask import send_file
        return send_file(abs_file_path)
    else:
        from flask import abort
        abort(404)

if __name__ == "__main__":
    app.run(debug=True)
