from flask import Flask, render_template, request, redirect, url_for, session
import os
from db import find_similar_items, get_item_by_id
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "your_secret_key"
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


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
            user_photo = "/" + filepath
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


if __name__ == "__main__":
    app.run(debug=True)
