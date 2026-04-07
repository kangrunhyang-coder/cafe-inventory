import os
from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, Product, StockRecord, Order
from datetime import datetime, date

app = Flask(__name__)

database_url = os.environ.get("DATABASE_URL", "sqlite:///cafe_inventory.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "cafe-inventory-secret-key")

db.init_app(app)

INITIAL_PRODUCTS = [
    # コーヒー豆
    {"name": "ブレンド豆", "category": "コーヒー豆", "unit": "kg", "stock_quantity": 5, "min_stock": 3, "supplier": "山田珈琲商事"},
    {"name": "ブラジル豆", "category": "コーヒー豆", "unit": "kg", "stock_quantity": 3, "min_stock": 2, "supplier": "山田珈琲商事"},
    {"name": "コロンビア豆", "category": "コーヒー豆", "unit": "kg", "stock_quantity": 1, "min_stock": 2, "supplier": "山田珈琲商事"},
    # ケーキ材料
    {"name": "いちご", "category": "ケーキ材料", "unit": "パック", "stock_quantity": 2, "min_stock": 3, "supplier": "近藤青果"},
    {"name": "生クリーム", "category": "ケーキ材料", "unit": "個", "stock_quantity": 4, "min_stock": 3, "supplier": "大阪食材センター"},
    {"name": "スポンジ粉", "category": "ケーキ材料", "unit": "kg", "stock_quantity": 1, "min_stock": 2, "supplier": "大阪食材センター"},
    {"name": "グラニュー糖", "category": "ケーキ材料", "unit": "kg", "stock_quantity": 3, "min_stock": 2, "supplier": "大阪食材センター"},
    {"name": "バター", "category": "ケーキ材料", "unit": "個", "stock_quantity": 5, "min_stock": 3, "supplier": "大阪食材センター"},
    # 消耗品
    {"name": "紙ナプキン", "category": "消耗品", "unit": "パック", "stock_quantity": 10, "min_stock": 5, "supplier": "まとめ買い問屋"},
    {"name": "コーヒーフィルター", "category": "消耗品", "unit": "箱", "stock_quantity": 2, "min_stock": 3, "supplier": "まとめ買い問屋"},
    {"name": "テイクアウト用カップ", "category": "消耗品", "unit": "箱", "stock_quantity": 3, "min_stock": 5, "supplier": "まとめ買い問屋"},
]


def init_db():
    db.create_all()
    if Product.query.count() == 0:
        for p in INITIAL_PRODUCTS:
            db.session.add(Product(**p))
        db.session.commit()


# --- Routes ---

@app.route("/")
def index():
    products = Product.query.all()
    low_stock = [p for p in products if p.status in ("low_stock", "out_of_stock")]
    total = len(products)
    ok_count = sum(1 for p in products if p.status == "in_stock")
    low_count = sum(1 for p in products if p.status == "low_stock")
    out_count = sum(1 for p in products if p.status == "out_of_stock")
    # お知らせ生成
    announcements = []
    today = date.today().strftime("%-m/%-d")
    if low_stock:
        announcements.append(f"{today}　発注が必要な商品が{len(low_stock)}件あります。確認してください。")
    out_items = [p for p in products if p.status == "out_of_stock"]
    if out_items:
        names = "・".join(p.name for p in out_items)
        announcements.append(f"{today}　在庫切れ：{names}。至急補充をお願いします。")
    pending_count = Order.query.filter_by(status="pending").count()
    if pending_count:
        announcements.append(f"{today}　未発注の注文が{pending_count}件あります。発注リストを確認してください。")
    ordered_count = Order.query.filter_by(status="ordered").count()
    if ordered_count:
        announcements.append(f"{today}　入荷待ちの発注が{ordered_count}件あります。")
    if not announcements:
        announcements.append(f"{today}　すべての在庫は正常です。")

    return render_template(
        "index.html",
        low_stock=low_stock,
        total=total,
        ok_count=ok_count,
        low_count=low_count,
        out_count=out_count,
        announcements=announcements,
    )


@app.route("/inventory")
def inventory():
    category = request.args.get("category", "")
    search = request.args.get("search", "").strip()
    query = Product.query
    if category:
        query = query.filter_by(category=category)
    if search:
        query = query.filter(Product.name.contains(search))
    products = query.all()
    categories = db.session.query(Product.category).distinct().all()
    categories = [c[0] for c in categories]
    return render_template(
        "inventory.html",
        products=products,
        categories=categories,
        selected_category=category,
        search=search,
    )


@app.route("/stock_record", methods=["GET", "POST"])
def stock_record():
    if request.method == "POST":
        product_id = int(request.form["product_id"])
        record_type = request.form["record_type"]
        quantity = int(request.form["quantity"])
        note = request.form.get("note", "")

        product = Product.query.get_or_404(product_id)

        if record_type == "out" and product.stock_quantity < quantity:
            flash("在庫数が足りません。", "error")
            return redirect(url_for("stock_record"))

        recorded_by = request.form["recorded_by"]

        record = StockRecord(
            product_id=product_id,
            record_type=record_type,
            quantity=quantity,
            recorded_by=recorded_by,
            note=note,
        )
        if record_type == "in":
            product.stock_quantity += quantity
        else:
            product.stock_quantity -= quantity

        db.session.add(record)
        db.session.commit()

        type_label = "入庫" if record_type == "in" else "出庫"
        flash(f"{product.name}の{type_label}を{quantity}{product.unit}記録しました。", "success")
        return redirect(url_for("stock_record"))

    products = Product.query.order_by(Product.category, Product.name).all()
    records = StockRecord.query.order_by(StockRecord.created_at.desc()).limit(50).all()
    return render_template("stock_record.html", products=products, records=records)


@app.route("/order_list", methods=["GET", "POST"])
def order_list():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "create":
            product_id = int(request.form["product_id"])
            quantity = int(request.form["quantity"])
            created_by = request.form["created_by"]
            order = Order(product_id=product_id, quantity=quantity, created_by=created_by)
            db.session.add(order)
            db.session.commit()
            flash("発注リストに追加しました。", "success")

        elif action == "mark_ordered":
            order_id = int(request.form["order_id"])
            ordered_by = request.form["ordered_by"]
            order = Order.query.get_or_404(order_id)
            order.status = "ordered"
            order.ordered_by = ordered_by
            order.ordered_at = datetime.now()
            db.session.commit()
            flash("発注済みに更新しました。", "success")

        elif action == "mark_received":
            order_id = int(request.form["order_id"])
            received_by = request.form["received_by"]
            order = Order.query.get_or_404(order_id)
            order.status = "received"
            order.received_by = received_by
            order.received_at = datetime.now()
            product = order.product
            product.stock_quantity += order.quantity
            db.session.commit()
            flash(f"{product.name}を{order.quantity}{product.unit}入庫しました。", "success")

        elif action == "delete":
            order_id = int(request.form["order_id"])
            order = Order.query.get_or_404(order_id)
            db.session.delete(order)
            db.session.commit()
            flash("発注を削除しました。", "success")

        return redirect(url_for("order_list"))

    pending_orders = Order.query.filter_by(status="pending").order_by(Order.created_at.desc()).all()
    ordered_orders = Order.query.filter_by(status="ordered").order_by(Order.ordered_at.desc()).all()
    received_orders = Order.query.filter_by(status="received").order_by(Order.received_at.desc()).limit(20).all()
    low_stock_products = [p for p in Product.query.all() if p.status in ("low_stock", "out_of_stock")]
    products = Product.query.order_by(Product.category, Product.name).all()

    return render_template(
        "order_list.html",
        pending_orders=pending_orders,
        ordered_orders=ordered_orders,
        received_orders=received_orders,
        low_stock_products=low_stock_products,
        products=products,
    )


@app.route("/products")
def products():
    all_products = Product.query.order_by(Product.category, Product.name).all()
    categories = db.session.query(Product.category).distinct().all()
    categories = [c[0] for c in categories]
    return render_template("products.html", products=all_products, categories=categories)


@app.route("/products/add", methods=["POST"])
def product_add():
    name = request.form["name"].strip()
    category = request.form["category"].strip()
    new_category = request.form.get("new_category", "").strip()
    if new_category:
        category = new_category
    unit = request.form["unit"].strip()
    stock_quantity = int(request.form.get("stock_quantity", 0))
    min_stock = int(request.form.get("min_stock", 0))
    supplier = request.form["supplier"].strip()

    product = Product(
        name=name, category=category, unit=unit,
        stock_quantity=stock_quantity, min_stock=min_stock, supplier=supplier,
    )
    db.session.add(product)
    db.session.commit()
    flash(f"「{name}」を登録しました。", "success")
    return redirect(url_for("products"))


@app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def product_edit(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == "POST":
        product.name = request.form["name"].strip()
        category = request.form["category"].strip()
        new_category = request.form.get("new_category", "").strip()
        if new_category:
            category = new_category
        product.category = category
        product.unit = request.form["unit"].strip()
        product.min_stock = int(request.form["min_stock"])
        product.supplier = request.form["supplier"].strip()
        db.session.commit()
        flash(f"「{product.name}」を更新しました。", "success")
        return redirect(url_for("products"))
    categories = db.session.query(Product.category).distinct().all()
    categories = [c[0] for c in categories]
    return render_template("product_edit.html", product=product, categories=categories)


@app.route("/products/<int:product_id>/delete", methods=["POST"])
def product_delete(product_id):
    product = Product.query.get_or_404(product_id)
    name = product.name
    db.session.delete(product)
    db.session.commit()
    flash(f"「{name}」を削除しました。", "success")
    return redirect(url_for("products"))


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
