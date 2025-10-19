# app/models.py
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'Users'
    UserID = db.Column(db.Integer, primary_key=True)
    Username = db.Column(db.String(100), unique=True, nullable=False)
    PasswordHash = db.Column(db.String(255), nullable=False)
    Role = db.Column(db.String(50), nullable=False, default='cashier')

    def set_password(self, password):
        self.PasswordHash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.PasswordHash, password)

class Category(db.Model):
    __tablename__ = 'Categories'
    CategoryID = db.Column(db.Integer, primary_key=True)
    CategoryName = db.Column(db.String(100), unique=True, nullable=False)
    Description = db.Column(db.Text)
    Products = db.relationship('Product', backref='Category', lazy=True)

class Product(db.Model):
    __tablename__ = 'Products'
    ProductID = db.Column(db.Integer, primary_key=True)
    ProductName = db.Column(db.String(255), unique=True, nullable=False)
    Description = db.Column(db.Text)
    CategoryID = db.Column(db.Integer, db.ForeignKey('Categories.CategoryID'))
    Price = db.Column(db.Numeric(10, 2), nullable=False)
    StockQuantity = db.Column(db.Integer, nullable=False, default=0)
    Barcode = db.Column(db.String(100), unique=True, nullable=True)
    SupplierID = db.Column(db.Integer, db.ForeignKey('Suppliers.SupplierID'), nullable=True)
    LastUpdated = db.Column(db.TIMESTAMP, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class Customer(db.Model):
    __tablename__ = 'Customers'
    CustomerID = db.Column(db.Integer, primary_key=True)
    FirstName = db.Column(db.String(100), nullable=False)
    LastName = db.Column(db.String(100))
    Email = db.Column(db.String(255), unique=True)
    PhoneNumber = db.Column(db.String(20))
    Address = db.Column(db.Text)
    RegistrationDate = db.Column(db.TIMESTAMP, default=datetime.datetime.utcnow)

class Sale(db.Model):
    __tablename__ = 'Sales'
    SaleID = db.Column(db.Integer, primary_key=True)
    CustomerID = db.Column(db.Integer, db.ForeignKey('Customers.CustomerID'), nullable=True)
    SaleDate = db.Column(db.TIMESTAMP, default=datetime.datetime.utcnow)
    TotalAmount = db.Column(db.Numeric(10, 2), nullable=False)
    PaymentMethod = db.Column(db.String(50))
    Customer = db.relationship('Customer', backref='sales')
    SaleDetails = db.relationship('SaleDetail', backref='sale', cascade="all, delete-orphan")
    inventory_logs = db.relationship('InventoryLog', backref='sale', lazy=True)

class SaleDetail(db.Model):
    __tablename__ = 'SaleDetails'
    SaleDetailID = db.Column(db.Integer, primary_key=True)
    SaleID = db.Column(db.Integer, db.ForeignKey('Sales.SaleID'), nullable=False)
    ProductID = db.Column(db.Integer, db.ForeignKey('Products.ProductID'), nullable=False)
    Quantity = db.Column(db.Integer, nullable=False)
    UnitPrice = db.Column(db.Numeric(10, 2), nullable=False)
    TotalPrice = db.Column(db.Numeric(10, 2), nullable=False)
    Product = db.relationship('Product')

class Supplier(db.Model):
    __tablename__ = 'Suppliers'
    SupplierID = db.Column(db.Integer, primary_key=True)
    SupplierName = db.Column(db.String(255), nullable=False, unique=True)
    ContactName = db.Column(db.String(100))
    PhoneNumber = db.Column(db.String(20))
    Email = db.Column(db.String(255))
    Address = db.Column(db.Text)
    Products = db.relationship('Product', backref='Supplier', lazy=True)

class InventoryLog(db.Model):
    __tablename__ = 'InventoryLogs'
    LogID = db.Column(db.Integer, primary_key=True)
    ProductID = db.Column(db.Integer, db.ForeignKey('Products.ProductID'), nullable=False)
    SaleID = db.Column(db.Integer, db.ForeignKey('Sales.SaleID'), nullable=True)
    ChangeDate = db.Column(db.TIMESTAMP, default=datetime.datetime.utcnow)
    ChangeType = db.Column(db.String(50), nullable=False) # e.g., 'Sale', 'Manual Adjustment', 'Initial Stock'
    QuantityChange = db.Column(db.Integer, nullable=False)
    Notes = db.Column(db.Text)
    Product = db.relationship('Product', backref='inventory_logs')

class PurchaseOrder(db.Model):
    __tablename__ = 'PurchaseOrders'
    PO_ID = db.Column(db.Integer, primary_key=True)
    SupplierID = db.Column(db.Integer, db.ForeignKey('Suppliers.SupplierID'), nullable=False)
    OrderDate = db.Column(db.TIMESTAMP, default=datetime.datetime.utcnow)
    Status = db.Column(db.String(50), nullable=False, default='Pending') # Pending, Completed
    TotalCost = db.Column(db.Numeric(10, 2), nullable=True)
    Supplier = db.relationship('Supplier', backref='purchase_orders')
    Details = db.relationship('PurchaseOrderDetail', backref='purchase_order', cascade="all, delete-orphan")

class PurchaseOrderDetail(db.Model):
    __tablename__ = 'PurchaseOrderDetails'
    PODetail_ID = db.Column(db.Integer, primary_key=True)
    PO_ID = db.Column(db.Integer, db.ForeignKey('PurchaseOrders.PO_ID'), nullable=False)
    ProductID = db.Column(db.Integer, db.ForeignKey('Products.ProductID'), nullable=False)
    Quantity = db.Column(db.Integer, nullable=False)
    CostPerItem = db.Column(db.Numeric(10, 2), nullable=True) # Cost from supplier
    Product = db.relationship('Product')