# app/routes.py
import json
from functools import wraps
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, jsonify, Response, current_app)
from .models import db, Product, Category, Customer, Sale, SaleDetail, User, Supplier, InventoryLog, PurchaseOrder, PurchaseOrderDetail
from sqlalchemy import func
import datetime
from datetime import date, timedelta
import io
import csv
import socket
import threading
import time
import ipaddress
from flask_sock import Sock
from app import sock

bp = Blueprint('main', __name__)

# --- Configuration & Globals ---
TCP_HOST_PORT = 12345
BROADCAST_PORT = 12346
DISCOVERY_MESSAGE = b"barcode_server_discovery_request"
websocket_clients = set()
tcp_server_thread = None
broadcast_thread = None
stop_threads = threading.Event()

# --- Network Utilities ---
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def get_broadcast_address(ip):
    try:
        network = ipaddress.IPv4Interface(f"{ip}/24").network
        return str(network.broadcast_address)
    except Exception:
        print("[Warning] Could not calculate broadcast address, using '255.255.255.255'.")
        return '255.255.255.255'

# --- WebSocket Function ---
def broadcast_barcode(barcode_data):
    message = json.dumps({"type": "barcode", "data": barcode_data})
    disconnected_clients = set()
    for client in list(websocket_clients):
        try:
             print(f"[WebSocket] Broadcasting '{barcode_data}' to a client.")
             client.send(message)
        except Exception as e:
            print(f"[WebSocket] Error sending to client {client}: {e}. Removing client.")
            disconnected_clients.add(client)
    for client in disconnected_clients:
        websocket_clients.discard(client)

# --- Discovery Broadcast Thread ---
def broadcast_presence(host_ip, tcp_port, stop_event):
    broadcast_ip = get_broadcast_address(host_ip)
    broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    message = f"{DISCOVERY_MESSAGE.decode()}|{host_ip}|{tcp_port}".encode('utf-8')
    print(f"[Discovery] Starting broadcast: '{message.decode()}' to {broadcast_ip}:{BROADCAST_PORT}")
    while not stop_event.is_set():
        try:
            broadcast_socket.sendto(message, (broadcast_ip, BROADCAST_PORT))
        except Exception as e:
            if not stop_event.is_set():
                print(f"[Discovery] Broadcast error: {e}")
        stop_event.wait(timeout=3.0)
    broadcast_socket.close()
    print("[Discovery] Broadcast thread stopped.")

# --- TCP Listener Thread ---
def tcp_barcode_listener(host_ip, port, stop_event):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_socket.bind((host_ip, port))
        server_socket.listen(1)
        server_socket.settimeout(1.0)
        print(f"[TCP Listener] Started on {host_ip}:{port}")
        while not stop_event.is_set():
            try:
                conn, addr = server_socket.accept()
                print(f"[TCP] Phone connected from {addr}")
                barcode_buffer = ""
                conn.settimeout(1.0)
                try:
                    while not stop_event.is_set():
                        try:
                            data = conn.recv(1024)
                            if not data: break
                            barcode_buffer += data.decode('utf-8')
                            while '\n' in barcode_buffer:
                                barcode_data, barcode_buffer = barcode_buffer.split('\n', 1)
                                barcode_data = barcode_data.strip()
                                if barcode_data:
                                    print(f"[TCP] Received code: {barcode_data} from {addr}")
                                    broadcast_barcode(barcode_data)
                        except socket.timeout: continue
                        except ConnectionResetError: print(f"[-] Phone disconnected unexpectedly from {addr}."); break
                        except Exception as e: print(f"[TCP] Recv Error from {addr}: {e}"); break
                finally:
                    conn.close()
                    print(f"[TCP] Phone connection closed from {addr}")
            except socket.timeout: continue
            except Exception as e:
                if not stop_event.is_set(): print(f"[TCP Listener] Accept Error: {e}")
                time.sleep(0.5)
    finally:
        server_socket.close()
        print("[TCP Listener] Stopped.")

# --- Start Background Threads ---
def start_background_threads():
    global tcp_server_thread, broadcast_thread
    host_ip = get_local_ip()

    if tcp_server_thread is None or not tcp_server_thread.is_alive():
        stop_threads.clear()
        tcp_host_ip = '0.0.0.0'
        tcp_server_thread = threading.Thread(
            target=tcp_barcode_listener, args=(tcp_host_ip, TCP_HOST_PORT, stop_threads), daemon=True
        )
        tcp_server_thread.start()
        print(f"Attempting to start TCP listener thread on {tcp_host_ip}:{TCP_HOST_PORT}...")

    if broadcast_thread is None or not broadcast_thread.is_alive():
        if stop_threads.is_set(): stop_threads.clear()
        broadcast_thread = threading.Thread(
            target=broadcast_presence, args=(host_ip, TCP_HOST_PORT, stop_threads), daemon=True
        )
        broadcast_thread.start()
        print(f"Attempting to start UDP broadcast thread for IP {host_ip}...")

# --- WebSocket Route ---
@sock.route('/ws/barcode')
def barcode_ws(ws):
    print(f"[WebSocket] Browser connected: {request.remote_addr}")
    websocket_clients.add(ws)
    try:
        while True:
            message = ws.receive(timeout=60)
            if message:
                print(f"[WebSocket] Received message: {message}")
    except Exception as e:
        print(f"[WebSocket] Connection error or closed for {request.remote_addr}: {e}")
    finally:
        print(f"[WebSocket] Browser disconnected: {request.remote_addr}")
        websocket_clients.discard(ws)

# --- DECORATORS ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("You must be logged in to view this page.", "error")
            return redirect(url_for('main.login_route'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(role_name):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('role') != role_name:
                flash("You do not have permission to access this page.", "error")
                return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

# --- MAIN AND DASHBOARD ---
@bp.route('/')
@login_required
def index():
    # start_background_threads() # Called in run.py
    if session['role'] == 'cashier':
        return redirect(url_for('main.new_sale_route'))
    stats = {
        'total_products': Product.query.count(),
        'total_categories': Category.query.count(),
        'total_customers': Customer.query.count(),
        'low_stock_items': Product.query.filter(Product.StockQuantity < 10).count()
    }
    return render_template('index.html', title="Dashboard", stats=stats)

# --- PRODUCT ROUTES ---
@bp.route('/products')
@login_required
def show_products():
    products_query = Product.query.order_by(Product.ProductName).all()
    products_list = [{
        'ProductID': p.ProductID, 'ProductName': p.ProductName, 'Description': p.Description or '',
        'Category': {'CategoryName': p.Category.CategoryName if p.Category else 'N/A'},
        'Price': float(p.Price), 'StockQuantity': p.StockQuantity
    } for p in products_query]
    return render_template('products/products.html', title='Product Catalog', products=products_list)

@bp.route('/products/add_form')
@login_required
@role_required('admin')
def add_product_form():
    categories = Category.query.order_by(Category.CategoryName).all()
    suppliers = Supplier.query.order_by(Supplier.SupplierName).all()
    return render_template('products/_add_product_form.html', categories=categories, suppliers=suppliers)

@bp.route('/products/add', methods=['POST'])
@login_required
@role_required('admin')
def add_product_route():
    product_name = request.form.get('product_name')
    if not product_name: return jsonify({'success': False, 'message': 'Product name is required.'}), 400
    new_product = Product(
        ProductName=product_name, Description=request.form.get('description'),
        CategoryID=request.form.get('category_id', type=int), Price=request.form.get('price', type=float),
        StockQuantity=request.form.get('stock_quantity', type=int),
        SupplierID=request.form.get('supplier_id', type=int) if request.form.get('supplier_id') else None,
        Barcode=request.form.get('barcode') or None
    )
    db.session.add(new_product); db.session.commit()
    return jsonify({'success': True, 'message': f"Product '{product_name}' added successfully."})

@bp.route('/products/edit_form/<int:product_id>')
@login_required
@role_required('admin')
def edit_product_form(product_id):
    product = Product.query.get_or_404(product_id)
    categories = Category.query.order_by(Category.CategoryName).all()
    suppliers = Supplier.query.order_by(Supplier.SupplierName).all()
    return render_template('products/_edit_product_form.html', product=product, categories=categories, suppliers=suppliers)

@bp.route('/products/edit/<int:product_id>', methods=['POST'])
@login_required
@role_required('admin')
def edit_product_route(product_id):
    product = Product.query.get_or_404(product_id)
    product.Description = request.form.get('description')
    product.CategoryID = request.form.get('category_id', type=int)
    product.Price = request.form.get('price', type=float)
    product.StockQuantity = request.form.get('stock_quantity', type=int)
    product.SupplierID = request.form.get('supplier_id', type=int) if request.form.get('supplier_id') else None
    product.Barcode = request.form.get('barcode') or None
    db.session.commit()
    return jsonify({'success': True, 'message': f"Product '{product.ProductName}' updated successfully."})

# --- CATEGORY ROUTES ---
@bp.route('/categories')
@login_required
@role_required('admin')
def show_categories():
    categories = Category.query.order_by(Category.CategoryName).all()
    return render_template('categories/categories.html', title='Manage Categories', categories=categories)

@bp.route('/categories/add_form')
@login_required
@role_required('admin')
def add_category_form():
    return render_template('categories/_add_category_form.html')

@bp.route('/categories/add', methods=['POST'])
@login_required
@role_required('admin')
def add_category_route():
    name = request.form.get('category_name')
    if not name: return jsonify({'success': False, 'message': 'Category name is required.'}), 400
    if Category.query.filter_by(CategoryName=name).first(): return jsonify({'success': False, 'message': f"Category '{name}' already exists."}), 400
    new_cat = Category(CategoryName=name, Description=request.form.get('description', ''))
    db.session.add(new_cat); db.session.commit()
    return jsonify({'success': True, 'message': f"Category '{name}' added."})

@bp.route('/categories/edit_form/<int:category_id>')
@login_required
@role_required('admin')
def edit_category_form(category_id):
    category = Category.query.get_or_404(category_id)
    return render_template('categories/_edit_category_form.html', category=category)

@bp.route('/categories/edit/<int:category_id>', methods=['POST'])
@login_required
@role_required('admin')
def edit_category_route(category_id):
    cat = Category.query.get_or_404(category_id)
    new_name = request.form.get('category_name')
    if not new_name: return jsonify({'success': False, 'message': 'Category name cannot be empty.'}), 400
    existing = Category.query.filter(Category.CategoryID != category_id, Category.CategoryName == new_name).first()
    if existing: return jsonify({'success': False, 'message': f"Category '{new_name}' already exists."}), 400
    cat.CategoryName = new_name
    cat.Description = request.form.get('description', '')
    db.session.commit()
    return jsonify({'success': True, 'message': 'Category updated.'})

# --- CUSTOMER ROUTES ---
@bp.route('/customers')
@login_required
def show_customers():
    customers = Customer.query.order_by(Customer.LastName, Customer.FirstName).all()
    return render_template('customers/customers.html', title='Manage Customers', customers=customers)

@bp.route('/customers/add_form')
@login_required
@role_required('admin')
def add_customer_form():
    return render_template('customers/_add_customer_form.html')

@bp.route('/customers/add', methods=['POST'])
@login_required
@role_required('admin')
def add_customer_route():
    first = request.form.get('first_name'); email = request.form.get('email', '')
    if not first: return jsonify({'success': False, 'message': 'First name required.'}), 400
    if email and Customer.query.filter_by(Email=email).first(): return jsonify({'success': False, 'message': 'Email already exists.'}), 400
    new_cust = Customer(FirstName=first, LastName=request.form.get('last_name', ''), Email=email or None, PhoneNumber=request.form.get('phone_number', ''), Address=request.form.get('address', ''))
    db.session.add(new_cust); db.session.commit()
    return jsonify({'success': True, 'message': f"Customer '{first}' added."})

@bp.route('/customers/edit_form/<int:customer_id>')
@login_required
@role_required('admin')
def edit_customer_form(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    return render_template('customers/_edit_customer_form.html', customer=customer)

@bp.route('/customers/edit/<int:customer_id>', methods=['POST'])
@login_required
@role_required('admin')
def edit_customer_route(customer_id):
    cust = Customer.query.get_or_404(customer_id); first = request.form.get('first_name'); email = request.form.get('email', '')
    if not first: return jsonify({'success': False, 'message': 'First name required.'}), 400
    if email and email != cust.Email and Customer.query.filter_by(Email=email).first(): return jsonify({'success': False, 'message': 'Email already exists for another customer.'}), 400
    cust.FirstName = first; cust.LastName = request.form.get('last_name', ''); cust.Email = email or None; cust.PhoneNumber = request.form.get('phone_number', ''); cust.Address = request.form.get('address', '')
    db.session.commit()
    return jsonify({'success': True, 'message': 'Customer updated.'})

# --- SUPPLIER ROUTES ---
@bp.route('/suppliers')
@login_required
@role_required('admin')
def show_suppliers():
    suppliers = Supplier.query.order_by(Supplier.SupplierName).all()
    return render_template('suppliers/suppliers.html', title='Manage Suppliers', suppliers=suppliers)

@bp.route('/suppliers/add_form')
@login_required
@role_required('admin')
def add_supplier_form():
    return render_template('suppliers/_add_supplier_form.html')

@bp.route('/suppliers/add', methods=['POST'])
@login_required
@role_required('admin')
def add_supplier_route():
    name = request.form.get('supplier_name')
    if not name: return jsonify({'success': False, 'message': 'Supplier name required.'}), 400
    if Supplier.query.filter_by(SupplierName=name).first(): return jsonify({'success': False, 'message': 'Supplier name already exists.'}), 400
    new_supp = Supplier(SupplierName=name, ContactName=request.form.get('contact_name'), PhoneNumber=request.form.get('phone_number'), Email=request.form.get('email'), Address=request.form.get('address'))
    db.session.add(new_supp); db.session.commit()
    return jsonify({'success': True, 'message': f"Supplier '{name}' added."})

@bp.route('/suppliers/edit_form/<int:supplier_id>')
@login_required
@role_required('admin')
def edit_supplier_form(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    return render_template('suppliers/_edit_supplier_form.html', supplier=supplier)

@bp.route('/suppliers/edit/<int:supplier_id>', methods=['POST'])
@login_required
@role_required('admin')
def edit_supplier_route(supplier_id):
    supp = Supplier.query.get_or_404(supplier_id); new_name = request.form.get('supplier_name')
    if not new_name: return jsonify({'success': False, 'message': 'Supplier name required.'}), 400
    existing = Supplier.query.filter(Supplier.SupplierID != supplier_id, Supplier.SupplierName == new_name).first()
    if existing: return jsonify({'success': False, 'message': f"Supplier name '{new_name}' already exists."}), 400
    supp.SupplierName = new_name; supp.ContactName = request.form.get('contact_name'); supp.PhoneNumber = request.form.get('phone_number'); supp.Email = request.form.get('email'); supp.Address = request.form.get('address')
    db.session.commit()
    return jsonify({'success': True, 'message': 'Supplier updated.'})

# --- SALES, INVENTORY, PO ROUTES ---
@bp.route('/sales/new', methods=['GET', 'POST'])
@login_required
def new_sale_route():
    if request.method == 'POST':
        cart_data_json = request.form.get('cart_data'); customer_id_str = request.form.get('customer_id'); payment_method = request.form.get('payment_method')
        if not cart_data_json: flash("Cart data missing.", "error"); return redirect(url_for('main.new_sale_route'))
        items_sold = json.loads(cart_data_json)
        if not items_sold: flash("Cart is empty.", "info"); return redirect(url_for('main.new_sale_route'))
        customer_id = int(customer_id_str) if customer_id_str and customer_id_str.isdigit() else None
        try:
            new_sale = Sale(CustomerID=customer_id, TotalAmount=0, PaymentMethod=payment_method); db.session.add(new_sale); db.session.flush()
            total_sale_amount = 0
            for item in items_sold:
                product = Product.query.get(item['product_id'])
                if not product or product.StockQuantity < item['quantity']: raise Exception(f"Insufficient stock for {product.ProductName if product else 'Unknown'}.")
                product.StockQuantity -= item['quantity']
                line_total = product.Price * item['quantity']; total_sale_amount += line_total
                db.session.add(SaleDetail(SaleID=new_sale.SaleID, ProductID=item['product_id'], Quantity=item['quantity'], UnitPrice=product.Price, TotalPrice=line_total))
                db.session.add(InventoryLog(ProductID=item['product_id'], SaleID=new_sale.SaleID, ChangeType='Sale', QuantityChange=-item['quantity'], Notes=f"Sale ID: {new_sale.SaleID}"))
            new_sale.TotalAmount = total_sale_amount; db.session.commit()
            flash(f"Sale processed! ID: {new_sale.SaleID}", "success"); return redirect(url_for('main.sale_receipt_route', sale_id=new_sale.SaleID))
        except Exception as e: db.session.rollback(); flash(f"Error processing sale: {e}", "error"); return redirect(url_for('main.new_sale_route'))
    products = Product.query.filter(Product.StockQuantity > 0).order_by(Product.ProductName).all()
    customers = Customer.query.order_by(Customer.LastName, Customer.FirstName).all()
    return render_template('sales/new_sale.html', title='New Sale', products=products, customers=customers)

@bp.route('/sales/history')
@login_required
def sales_history_route():
    start_date_str = request.args.get('start_date'); end_date_str = request.args.get('end_date')
    query = Sale.query.options(db.joinedload(Sale.Customer))
    if start_date_str: query = query.filter(Sale.SaleDate >= datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date())
    if end_date_str: query = query.filter(Sale.SaleDate < (datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date() + timedelta(days=1)))
    sales_records = query.order_by(Sale.SaleDate.desc()).all()
    return render_template('sales/sales_history.html', title='Sales History', sales_records=sales_records)

@bp.route('/sales/details/<int:sale_id>')
@login_required
def sale_details_route(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    return render_template('sales/sale_details.html', title=f"Sale Details #{sale_id}", sale=sale, items=sale.SaleDetails)

@bp.route('/inventory/low_stock')
@login_required
@role_required('admin')
def low_stock_report_route():
    items = Product.query.filter(Product.StockQuantity < 10).order_by(Product.StockQuantity).all()
    return render_template('inventory/low_stock_report.html', title="Low Stock Report", items=items, threshold=10)

@bp.route('/inventory/adjust', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def inventory_adjustment_route():
    if request.method == 'POST':
        prod_id = request.form.get('product_id', type=int); qty_change = request.form.get('quantity_change', type=int); change_type = request.form.get('change_type')
        if not all([prod_id, qty_change is not None, change_type]): flash("All fields required.", "error")
        else:
            prod = Product.query.get(prod_id)
            if not prod: flash("Product not found.", "error")
            else:
                prod.StockQuantity += qty_change
                db.session.add(InventoryLog(ProductID=prod_id, ChangeType=change_type, QuantityChange=qty_change, Notes=request.form.get('notes')))
                db.session.commit(); flash(f"Stock for '{prod.ProductName}' updated.", "success"); return redirect(url_for('main.inventory_adjustment_route'))
    products = Product.query.order_by(Product.ProductName).all()
    return render_template('inventory/inventory_adjustment.html', products=products, title="Inventory Adjustment")

@bp.route('/purchase_orders')
@login_required
@role_required('admin')
def show_purchase_orders():
    pos = PurchaseOrder.query.order_by(PurchaseOrder.OrderDate.desc()).all()
    return render_template('purchase_orders/purchase_orders.html', purchase_orders=pos, title="Purchase Orders")

@bp.route('/purchase_orders/new', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def new_purchase_order_route():
    if request.method == 'POST':
        po_json = request.form.get('po_data'); supp_id = request.form.get('supplier_id', type=int)
        if not all([po_json, supp_id]): flash("Supplier and items required.", "error"); return redirect(url_for('main.new_purchase_order_route'))
        items = json.loads(po_json)
        try:
            new_po = PurchaseOrder(SupplierID=supp_id, Status='Pending'); db.session.add(new_po); db.session.flush()
            details = [PurchaseOrderDetail(PO_ID=new_po.PO_ID, ProductID=item['productId'], Quantity=item['quantity']) for item in items]
            db.session.add_all(details); db.session.commit()
            flash(f"PO #{new_po.PO_ID} created.", "success"); return redirect(url_for('main.show_purchase_orders'))
        except Exception as e: db.session.rollback(); flash(f"Error creating PO: {e}", "error")
    products = Product.query.order_by(Product.ProductName).all(); suppliers = Supplier.query.order_by(Supplier.SupplierName).all()
    return render_template('purchase_orders/new_purchase_order.html', products=products, suppliers=suppliers, title="New Purchase Order")

@bp.route('/purchase_orders/<int:po_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def purchase_order_details_route(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    if request.method == 'POST':
        if po.Status == 'Completed': flash("Order already completed.", "error")
        else:
            try:
                for detail in po.Details:
                    detail.Product.StockQuantity += detail.Quantity
                    db.session.add(InventoryLog(ProductID=detail.ProductID, ChangeType='Purchase Order', QuantityChange=detail.Quantity, Notes=f"PO #{po.PO_ID}"))
                po.Status = 'Completed'; db.session.commit(); flash(f"PO #{po.PO_ID} completed. Stock updated.", "success")
            except Exception as e: db.session.rollback(); flash(f"An error occurred: {e}", "error")
        return redirect(url_for('main.purchase_order_details_route', po_id=po.PO_ID))
    return render_template('purchase_orders/purchase_order_details.html', po=po, title=f"PO #{po.PO_ID} Details")

# --- AUTHENTICATION ROUTES ---
@bp.route('/login', methods=['GET', 'POST'])
def login_route():
    if 'user_id' in session: return redirect(url_for('main.index'))
    if request.method == 'POST':
        user = User.query.filter_by(Username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')):
            session['user_id'] = user.UserID; session['username'] = user.Username; session['role'] = user.Role
            flash(f"Welcome back, {user.Username}!", "success"); return redirect(url_for('main.index'))
        else: flash("Invalid username or password.", "error")
    return render_template('auth/login.html')

@bp.route('/logout')
def logout_route():
    session.clear(); flash("Logged out successfully.", "success")
    return redirect(url_for('main.login_route'))

@bp.route('/register', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def register_route():
    if request.method == 'POST':
        username = request.form.get('username')
        if User.query.filter_by(Username=username).first(): flash("Username already exists.", "error")
        else:
            new_user = User(Username=username, Role='cashier'); new_user.set_password(request.form.get('password'))
            db.session.add(new_user); db.session.commit(); flash(f"Cashier '{username}' created.", "success"); return redirect(url_for('main.index'))
    return render_template('auth/register.html')

@bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password_route():
    if request.method == 'POST':
        user = User.query.get(session['user_id'])
        if not user.check_password(request.form.get('current_password')): flash("Incorrect current password.", "error")
        elif request.form.get('new_password') != request.form.get('confirm_password'): flash("New passwords do not match.", "error")
        else:
            user.set_password(request.form.get('new_password')); db.session.commit()
            flash("Password updated successfully!", "success"); return redirect(url_for('main.index'))
    return render_template('auth/change_password.html', title="Change Password")

# --- API ROUTES ---
@bp.route('/api/products/search')
@login_required
def api_search_products():
    query = request.args.get('q', '')
    products_query = Product.query.filter(Product.ProductName.like(f"%{query}%")).order_by(Product.ProductName).limit(20).all()
    return jsonify([{
        'ProductID': p.ProductID, 'ProductName': p.ProductName, 'Description': p.Description or '',
        'Category': {'CategoryName': p.Category.CategoryName if p.Category else 'N/A'},
        'Price': float(p.Price), 'StockQuantity': p.StockQuantity
    } for p in products_query])

@bp.route('/api/products/<int:product_id>', methods=['DELETE'])
@login_required
@role_required('admin')
def api_delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    try: db.session.delete(product); db.session.commit(); return jsonify({'success': True, 'message': f"Product '{product.ProductName}' deleted."})
    except Exception as e:
        db.session.rollback(); msg = 'An unexpected error occurred.'
        if 'foreign key constraint' in str(e).lower(): msg = 'Cannot delete: product is part of an existing sale.'
        return jsonify({'success': False, 'message': msg}), 500 if 'constraint' not in msg else 400

@bp.route('/api/categories/<int:category_id>', methods=['DELETE'])
@login_required
@role_required('admin')
def api_delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    if category.Products: return jsonify({'success': False, 'message': f"Cannot delete '{category.CategoryName}': in use by products."}), 400
    try: db.session.delete(category); db.session.commit(); return jsonify({'success': True, 'message': f"Category '{category.CategoryName}' deleted."})
    except Exception: db.session.rollback(); return jsonify({'success': False, 'message': 'An unexpected error occurred.'}), 500

@bp.route('/api/customers/<int:customer_id>', methods=['DELETE'])
@login_required
@role_required('admin')
def api_delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id); name = f"{customer.FirstName} {customer.LastName or ''}".strip()
    try: db.session.delete(customer); db.session.commit(); return jsonify({'success': True, 'message': f"Customer '{name}' deleted."})
    except Exception: db.session.rollback(); return jsonify({'success': False, 'message': 'An unexpected error occurred.'}), 500

@bp.route('/api/suppliers/<int:supplier_id>', methods=['DELETE'])
@login_required
@role_required('admin')
def api_delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    if supplier.Products: return jsonify({'success': False, 'message': f"Cannot delete '{supplier.SupplierName}': linked to products."}), 400
    try: db.session.delete(supplier); db.session.commit(); return jsonify({'success': True, 'message': f"Supplier '{supplier.SupplierName}' deleted."})
    except Exception: db.session.rollback(); return jsonify({'success': False, 'message': 'An unexpected error occurred.'}), 500

@bp.route('/api/sales/last_7_days')
@login_required
def sales_last_7_days_api():
    try:
        start = date.today() - timedelta(days=6)
        data = db.session.query(
            func.date(Sale.SaleDate).label('d'),
            func.sum(Sale.TotalAmount).label('t')
        ).filter(Sale.SaleDate >= start)\
         .group_by(func.date(Sale.SaleDate))\
         .order_by(func.date(Sale.SaleDate))\
         .all()
        sales = { (start + timedelta(days=i)).strftime('%Y-%m-%d'): 0 for i in range(7) }
        for row in data:
            if isinstance(row[0], datetime.date):
                day_str = row[0].strftime('%Y-%m-%d')
                if day_str in sales:
                    sales[day_str] = float(row[1] or 0)
            else:
                current_app.logger.warning(f"Unexpected type for date aggregation: {type(row[0])}, value: {row[0]}")
        return jsonify({'labels': list(sales.keys()), 'data': list(sales.values())})
    except Exception as e:
        current_app.logger.error(f"Error in sales_last_7_days_api: {e}", exc_info=True)
        return jsonify({"error": "Internal server error fetching sales data"}), 500

@bp.route('/api/sales/by_category')
@login_required
@role_required('admin')
def sales_by_category_api():
    try:
        data = db.session.query(
            Category.CategoryName,
            func.sum(SaleDetail.TotalPrice).label('r')
        ).select_from(SaleDetail)\
         .join(Product, SaleDetail.ProductID == Product.ProductID)\
         .join(Category, Product.CategoryID == Category.CategoryID)\
         .group_by(Category.CategoryName)\
         .order_by(func.sum(SaleDetail.TotalPrice).desc())\
         .all()
        labels = [r.CategoryName for r in data]
        values = [float(r.r or 0) for r in data]
        return jsonify({'labels': labels, 'data': values})
    except Exception as e:
        current_app.logger.error(f"Error in sales_by_category_api: {e}", exc_info=True)
        return jsonify({"error": "Internal server error fetching category sales"}), 500


@bp.route('/api/products/best_sellers')
@login_required
@role_required('admin')
def best_sellers_api():
    try:
        sellers = db.session.query(
            Product.ProductName,
            func.sum(SaleDetail.Quantity).label('s')
        ).select_from(SaleDetail)\
         .join(Product, SaleDetail.ProductID == Product.ProductID)\
         .group_by(Product.ProductName)\
         .order_by(func.sum(SaleDetail.Quantity).desc())\
         .limit(5)\
         .all()
        return jsonify({'labels': [r.ProductName for r in sellers], 'data': [int(r.s or 0) for r in sellers]})
    except Exception as e:
        current_app.logger.error(f"Error in best_sellers_api: {e}", exc_info=True)
        return jsonify({"error": "Internal server error fetching best sellers"}), 500


@bp.route('/customers/<int:customer_id>/history')
@login_required
@role_required('admin')
def customer_history_route(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    sales = Sale.query.filter_by(CustomerID=customer_id).order_by(Sale.SaleDate.desc()).all()
    return render_template('customers/customer_history.html', title='Purchase History', customer=customer, sales=sales)

@bp.route('/sales/receipt/<int:sale_id>')
@login_required
def sale_receipt_route(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    return render_template('sales/receipt.html', title=f"Receipt #{sale_id}", sale=sale)

@bp.route('/api/products/by_barcode/<string:barcode>')
@login_required
def api_product_by_barcode(barcode):
    prod = Product.query.filter_by(Barcode=barcode).first()
    if prod: return jsonify({'ProductID': prod.ProductID, 'ProductName': prod.ProductName, 'Price': float(prod.Price), 'StockQuantity': prod.StockQuantity})
    return jsonify({'error': 'Product not found'}), 404

@bp.route('/export/low_stock_csv')
@login_required
@role_required('admin')
def export_low_stock_csv():
    items = Product.query.filter(Product.StockQuantity < 10).order_by(Product.StockQuantity).all()
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Stock', 'Price'])
    for i in items: writer.writerow([i.ProductID, i.ProductName, i.StockQuantity, i.Price])
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=low_stock.csv"})

@bp.route('/export/sales_csv')
@login_required
@role_required('admin')
def export_sales_csv():
    start = request.args.get('start_date'); end = request.args.get('end_date')
    query = Sale.query.options(db.joinedload(Sale.Customer))
    if start: query = query.filter(Sale.SaleDate >= datetime.datetime.strptime(start, '%Y-%m-%d').date())
    if end: query = query.filter(Sale.SaleDate < (datetime.datetime.strptime(end, '%Y-%m-%d').date() + timedelta(days=1)))
    sales = query.order_by(Sale.SaleDate.desc()).all()
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(['ID', 'Date', 'Customer', 'Total', 'Payment Method'])
    for s in sales: writer.writerow([s.SaleID, s.SaleDate.strftime('%Y-%m-%d %H:%M:%S'), f"{s.Customer.FirstName} {s.Customer.LastName or ''}" if s.Customer else "Guest", s.TotalAmount, s.PaymentMethod])
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=sales.csv"})

# --- ADMIN ROUTES ---
@bp.route('/admin/wipe_db_form')
@login_required
@role_required('admin')
def wipe_db_form():
    return render_template('admin/_wipe_db_form.html')

@bp.route('/admin/wipe_database', methods=['POST'])
@login_required
@role_required('admin')
def wipe_database():
    pwd = request.form.get('password'); user = User.query.get(session['user_id'])
    if not user or not user.check_password(pwd): return jsonify({'success': False, 'message': 'Incorrect password.'}), 403
    try:
        db.session.query(SaleDetail).delete(); db.session.query(InventoryLog).delete(); db.session.query(PurchaseOrderDetail).delete()
        db.session.flush()
        db.session.query(Sale).delete(); db.session.query(PurchaseOrder).delete()
        db.session.flush()
        db.session.query(Product).delete()
        db.session.flush()
        db.session.query(Category).delete(); db.session.query(Supplier).delete(); db.session.query(Customer).delete()
        db.session.flush()
        db.session.query(User).filter(User.Role != 'admin').delete()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Database wiped. Admin users preserved.'})
    except Exception as e:
        db.session.rollback(); return jsonify({'success': False, 'message': f'Error: {e}'}), 500