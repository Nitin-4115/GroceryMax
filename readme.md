# 🛒 GroceryMax: Grocery Store Management System

## 📘 Description

GroceryMax is a web-based stock management system designed for small to medium-sized grocery or retail stores. It replaces manual inventory tracking with a centralized, database-driven system, improving efficiency and accuracy.

The application provides:

  - Inventory control
  - Point-of-sale (POS) transactions
  - Supplier and customer management
  - Purchase orders
  - Reporting and analytics

Built with Python (Flask) and SQLAlchemy ORM, GroceryMax offers a clean and intuitive interface using Bootstrap, and implements role-based access control for Administrators and Cashiers.

## 🚀 Features

  - **Role-Based Access Control**: Secure login for Admin and Cashier roles with distinct permissions.
  - **Dashboard (Admin)**: Overview of sales analytics, top products, and key statistics.
  - **Product Management (Admin)**: Full CRUD operations for products (price, stock, category, supplier, barcode).
  - **Catalog Management (Admin)**: CRUD operations for categories and suppliers.
  - **Customer Management (Admin)**: CRUD operations for customer records and viewing purchase history.
  - **Point of Sale (POS)**:
      - Add items via search or simulated barcode scan (WebSocket)
      - Cart management and optional customer association
      - Finalize transactions easily
  - **Inventory Control**:
      - Automatic stock decrement on sale
      - Automatic stock increment on purchase order completion
      - Manual adjustments for damaged or lost items
      - Low Stock Report for items below threshold
  - **Purchase Orders (Admin)**: Create, view, and complete purchase orders for restocking.
  - **Reporting (Admin)**: Filterable sales history, low stock items, and export to CSV.
  - **Database Management**: Schema migrations handled with Flask-Migrate and Alembic.

## 📱 Mobile Barcode Scanner

This repository includes a companion **Android App (`barcode_scanner.apk`)**.

This app allows you to use your smartphone's camera as a wireless barcode scanner for the POS system.

  - **How it works:** The Flask application runs a TCP server that bridges to a WebSocket. The Android app connects to this server over your local WiFi and sends barcode data directly to the "New Sale" page in real-time.
  - **Setup:**
    1.  Install the `barcode_scanner.apk` on an Android device.
    2.  Ensure your phone is on the **same WiFi network** as the computer running the Flask server.
    3.  The app will automatically discover the server. Once connected, any barcode you scan will be sent to the POS.

## 🧰 Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, Flask |
| Database | MySQL |
| ORM | SQLAlchemy (Flask-SQLAlchemy) |
| Migrations | Flask-Migrate (Alembic) |
| Authentication | Flask-Login |
| Forms | Flask-WTF |
| Real-Time | Flask-Sock (WebSocket for barcode simulation) |
| Frontend | HTML, CSS, JavaScript |
| UI Framework | Bootstrap 5 + Tailwind CSS utilities |
| Charts | Chart.js |
| Dependencies | Listed in `requirements.txt` |

## ⚙️ Setup Instructions

### 1️⃣ Prerequisites

Make sure you have:

  - Python 3.10 or later
  - `pip` (Python package manager)
  - `git`
  - MySQL Server installed and running

### 2️⃣ Clone the Repository

```bash
git clone <your-repository-url>
cd GroceryMax
```

### 3️⃣ Configure Environment Variables

Create a `.env` file in the project root (`GroceryMax/`) and add the following:

```ini
DB_HOST="localhost"
DB_NAME="grocerymaxdb"
DB_USER="your_mysql_username"
DB_PASSWORD="your_mysql_password"
FLASK_SECRET_KEY="a_very_secret_random_key"
```

### 4️⃣ Create a Virtual Environment

```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

### 5️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 6️⃣ Set Up the Database

Ensure your MySQL server is running, then create the database:

```sql
CREATE DATABASE grocerymaxdb;
```

Initialize the schema and apply migrations:

```bash
flask db init # Run once (if 'migrations' folder doesn't exist)
flask db migrate -m "Initial database setup"
flask db upgrade
```

### 7️⃣ Seed Initial Data (Optional)

Run the seed script to create a default admin and sample data:

```bash
python seed.py
```

**Default Admin Login**

```
Username: admin
Password: admin123
```

⚠️ Change this password immediately after first login.

### 8️⃣ Run the Application

```bash
python run.py
```

Open your browser:

  - [http://127.0.0.1:5000](http://127.0.0.1:5000)
  - or [http://0.0.0.0:5000](http://0.0.0.0:5000)

## 💻 Usage Guide

| Role | Access |
|---|---|
| Admin | Full access (Dashboard, Products, Categories, Suppliers, Customers, Inventory, Purchase Orders, Reports, Register User) |
| Cashier | Limited access (New Sale, View Products, View Customers, Sales History) |

## 🧠 Default Roles (if seeded)

| Role | Username | Password | Access |
|---|---|---|---|
| Admin | admin | admin123 | Full Access |
| Cashier | cashier | cashier123 | POS & Sales |

*(You can change these in the database or seed file.)*

## 🧮 Database Schema (Overview)

**Entities:**

  - Users → (UserID, Username, Password, Role)
  - Products → (ProductID, Name, CategoryID, SupplierID, Price, Quantity, Barcode)
  - Categories → (CategoryID, CategoryName)
  - Suppliers → (SupplierID, Name, Contact, Email)
  - Customers → (CustomerID, Name, Email, Phone)
  - Sales → (SaleID, Date, Total, UserID, CustomerID)
  - SaleItems → (SaleItemID, SaleID, ProductID, Quantity, Price)
  - PurchaseOrders → (OrderID, SupplierID, OrderDate, Status)
  - PurchaseItems → (ItemID, OrderID, ProductID, Quantity, Cost)

## 🧑‍💻 Project Structure

```
GroceryMax/
├── app/
│ ├── init.py
│ ├── routes.py
│ ├── models.py
│ ├── forms.py
│ ├── templates/
│ ├── static/
│ └── utils/
├── migrations/
├── .env
├── requirements.txt
├── config.py
├── seed_data.py
└── run.py
```

## 🧾 Example .env Configuration

```ini
DB_HOST=localhost
DB_NAME=grocerymaxdb
DB_USER=root
DB_PASSWORD=12345
FLASK_SECRET_KEY=mysecretkey
```

## 📊 Dashboard Visuals

The Admin dashboard includes:

  - Total daily/weekly/monthly sales
  - Graphs powered by Chart.js
  - Alerts for low-stock products

## 🧱 Future Enhancements

  - Barcode scanner hardware integration
  - Cloud database support (AWS RDS)
  - Expense and profit tracking
  - Email notification system
  - Mobile-responsive POS view

## 🤝 Contributing

1.  Fork the repository
2.  Create your feature branch:
    ```bash
    git checkout -b feature/new-feature
    ```
3.  Commit your changes:
    ```bash
    git commit -m "Add new feature"
    ```
4.  Push to the branch:
    ```bash
    git push origin feature/new-feature
    ```
5.  Submit a Pull Request

## 🧑‍🏫 Author

**Developed by:** Nitin L
**GitHub:** [https://github.com/Nitin-4115](https://github.com/Nitin-4115)