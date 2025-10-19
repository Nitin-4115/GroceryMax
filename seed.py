# seed.py
from app import create_app
from app.models import db, Category, Product, Customer, User

# Create a Flask app context to work with the database
app = create_app()
ctx = app.app_context()
ctx.push()

def seed_data():
    """Seeds the database with initial data if it's empty."""

    # --- Create Admin User ---
    if User.query.count() == 0:
        print("No users found. Creating default admin user...")
        admin = User(Username='<username>', Role='admin')
        admin.set_password('<a-very-strong-password>') # Set a default password
        db.session.add(admin)
        print("Admin user created with username: 'admin' and password: '4115'")
    else:
        print("Users already exist. Skipping admin creation.")

    # --- Seed Categories ---
    if Category.query.count() == 0:
        print("Seeding categories...")
        cat_fruits = Category(CategoryName="Fruits", Description="Fresh and juicy fruits")
        cat_veg = Category(CategoryName="Vegetables", Description="Farm fresh vegetables")
        cat_dairy = Category(CategoryName="Dairy", Description="Milk, cheese, yogurt, etc.")
        cat_bakery = Category(CategoryName="Bakery", Description="Freshly baked goods")
        db.session.add_all([cat_fruits, cat_veg, cat_dairy, cat_bakery])
    else:
        print("Categories already exist. Skipping.")

    # --- Seed Products ---
    if Product.query.count() == 0:
        print("Seeding products...")
        # Get categories again to ensure they are session-bound
        cat_fruits = Category.query.filter_by(CategoryName="Fruits").first()
        cat_veg = Category.query.filter_by(CategoryName="Vegetables").first()
        
        p1 = Product(ProductName="Organic Apples", Description="Crisp Fuji variety", Category=cat_fruits, Price=0.75, StockQuantity=150)
        p2 = Product(ProductName="Bananas", Description="Bunch of 5, ripe", Category=cat_fruits, Price=1.99, StockQuantity=200)
        p3 = Product(ProductName="Carrots", Description="1lb bag, organic", Category=cat_veg, Price=1.29, StockQuantity=8)
        db.session.add_all([p1, p2, p3])
    else:
        print("Products already exist. Skipping.")
    
    db.session.commit()
    print("\nDatabase seeding check complete!")


if __name__ == '__main__':
    seed_data()
    ctx.pop()