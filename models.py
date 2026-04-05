from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    min_stock = db.Column(db.Integer, nullable=False, default=0)
    supplier = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    records = db.relationship("StockRecord", backref="product", lazy=True)
    orders = db.relationship("Order", backref="product", lazy=True)

    @property
    def status(self):
        if self.stock_quantity <= 0:
            return "out_of_stock"
        elif self.stock_quantity <= self.min_stock:
            return "low_stock"
        return "in_stock"

    @property
    def status_label(self):
        labels = {
            "out_of_stock": "在庫切れ",
            "low_stock": "残りわずか",
            "in_stock": "在庫あり",
        }
        return labels[self.status]


class StockRecord(db.Model):
    __tablename__ = "stock_records"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    record_type = db.Column(db.String(10), nullable=False)  # "in" or "out"
    quantity = db.Column(db.Integer, nullable=False)
    recorded_by = db.Column(db.String(50), nullable=False, default="")
    note = db.Column(db.String(200), default="")
    created_at = db.Column(db.DateTime, default=datetime.now)


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending / ordered / received
    created_by = db.Column(db.String(50), nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.now)
    ordered_by = db.Column(db.String(50), nullable=False, default="")
    ordered_at = db.Column(db.DateTime, nullable=True)
    received_by = db.Column(db.String(50), nullable=False, default="")
    received_at = db.Column(db.DateTime, nullable=True)

    @property
    def status_label(self):
        labels = {
            "pending": "未発注",
            "ordered": "発注済",
            "received": "受取済",
        }
        return labels.get(self.status, self.status)
