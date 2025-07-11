from flask import Flask, render_template, redirect, url_for, request
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from flask_bcrypt import Bcrypt

from werkzeug.utils import secure_filename
from flask_migrate import Migrate
import os
from datetime import datetime
from bson import ObjectId


from bson.errors import InvalidId




app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'  # Set upload folder path
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}  # Allowed file types

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.config["MONGO_URI"] = "mongodb+srv://sreejith:sreejith123@cluster0.gcfd31y.mongodb.net/ecommerce?retryWrites=true&w=majority"
mongo = PyMongo(app)
app.config['SECRET_KEY'] = 'your_secret_key'
bcrypt = Bcrypt(app)




@app.route('/')
def index():
    return redirect(url_for('home'))

@app.route('/home')

def home():
    products = list(mongo.db.products.find())
    return render_template('home.html', products=products)







from bson import ObjectId

@app.route('/admin')
def admin_dashboard():
    

    total_users = mongo.db.users.count_documents({})
    total_products = mongo.db.products.count_documents({})
    total_orders = mongo.db.orders.count_documents({})
    orders = list(mongo.db.orders.find())

    for order in orders:
        # Convert user_id to ObjectId if needed for query
        user_id = order.get('user_id')
        if user_id and not isinstance(user_id, ObjectId):
            try:
                user_id = ObjectId(user_id)
            except:
                user_id = None
        user = mongo.db.users.find_one({'_id': user_id}) if user_id else None
        order['user'] = user['email'] if user else 'N/A'

        # Keep the full items list
        order['items'] = order.get('items', [])

        # Prepare full address string from nested address dict
        addr = order.get('address', {})
        address_parts = [
            addr.get('street', ''),
            addr.get('city', ''),
            addr.get('state', ''),
            addr.get('zip_code', ''),
            addr.get('country', '')
        ]
        order['address'] = ', '.join([part for part in address_parts if part])

        order['status'] = order.get('status', 'Pending')

    return render_template(
        'admin_dashboard.html',
        total_users=total_users,
        total_products=total_products,
        total_orders=total_orders,
        orders=orders
    )



@app.route('/add-address', methods=['GET', 'POST'])
def add_address():
    product_id = request.args.get('product_id')  # For single product checkout

    if request.method == 'POST':
        # Get address form data
        full_name = request.form['full_name']
        phone = request.form['phone']
        street = request.form['street']
        city = request.form['city']
        state = request.form['state']
        zip_code = request.form['zip_code']
        country = request.form['country']

        # Create address dictionary
        address = {
            
            'full_name': full_name,
            'phone': phone,
            'street': street,
            'city': city,
            'state': state,
            'zip_code': zip_code,
            'country': country
        }

        # Optional: Save address to 'addresses' collection
        mongo.db.addresses.insert_one(address)

        items = []

        # Determine items: single product or full cart
        if product_id:
            product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
            if not product:
                flash('Product not found.', 'danger')
                return redirect(url_for('home'))
            items.append({
                'product_id': str(product['_id']),
                'name': product['name'],
                'price': product['price'],
                'quantity': 1
            })
        else:
            cart_items = list(mongo.db.cart.find())
            if not cart_items:
                flash("Your cart is empty.", "danger")
                return redirect(url_for('home'))

            for item in cart_items:
                product = mongo.db.products.find_one({'_id': ObjectId(item['product_id'])})
                if product:
                    items.append({
                        'product_id': str(product['_id']),
                        'name': product['name'],
                        'price': product['price'],
                        'quantity': item['quantity']
                    })

        # Calculate total price
        total_price = sum(item['price'] * item['quantity'] for item in items)

        # Create the order
        order = {
            
            'items': items,
            'address': address,
            'status': 'Pending',
            'total_price': total_price
        }

        result = mongo.db.orders.insert_one(order)
        order_id = str(result.inserted_id)

        # Clear cart if it was a full cart checkout
        if not product_id:
            mongo.db.cart.delete_many({})

        flash('Order placed successfully!', 'success')
        return redirect(url_for('order_success', order_id=order_id))

    return render_template('add_address.html', product_id=product_id)



@app.route('/order/<order_id>/update', methods=['POST'])
def update_order(order_id):
    

    order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})
    if not order:
        abort(404)

    new_status = request.form['status']
    mongo.db.orders.update_one({'_id': ObjectId(order_id)}, {'$set': {'status': new_status}})
    
    return redirect(url_for('admin_dashboard'))



from bson import ObjectId

@app.route('/admin/addresses')
def view_addresses():
    orders = list(mongo.db.orders.find())
    orders_with_products = []

    for order in orders:
        # Get product_id safely
        product_id = order.get('product_id')
        if not product_id:
            continue  # Skip this order if product_id is missing

        user = mongo.db.users.find_one({'_id': order.get('user_id')})
        product = mongo.db.products.find_one({'_id': ObjectId(product_id)})

        orders_with_products.append({
            'order': order,
            'user': user,
            'product': product
        })

    return render_template('admin_addresses.html', orders_with_products=orders_with_products)



@app.route('/pay/<product_id>', methods=['GET', 'POST'])
def pay(product_id):
    try:
        product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
    except:
        flash("Invalid product ID.", "danger")
        return redirect(url_for('home'))

    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for('home'))

    # (Integrate payment gateway here if needed)
    return render_template('order_success.html', product=product)



@app.route('/admin/users')
def view_users():
   

    users = list(mongo.db.users.find())  # Get all registered users
    return render_template('admin_users.html', users=users)

@app.route('/admin/orders')
def view_all_orders():
    

    orders = list(mongo.db.orders.find())
    products = {str(p['_id']): p for p in mongo.db.products.find()}
    users = {str(u['_id']): u for u in mongo.db.users.find()}

    return render_template('admin_orders.html', orders=orders, products=products, users=users)



@app.route('/admin/add-product', methods=['GET', 'POST'])
def add_product():
    

    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        status = request.form['status']

        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_path = f"uploads/{filename}"

        mongo.db.products.insert_one({
            'name': name,
            'price': price,
            'status': status,
            'image': image_path
        })
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_add_product.html')

@app.route('/order-success')
def order_success():
    order_id = request.args.get('order_id')  # get order_id from URL query param
    product_id = request.args.get('product_id')  # optional if direct product checkout

    order = None
    if order_id:
        order = mongo.db.orders.find_one({'_id': ObjectId(order_id)})

    return render_template('order_success.html', order=order, product_id=product_id, order_id=order_id)





@app.route('/add-to-cart', methods=['POST'])
def add_to_cart():
    product_id = request.form.get('product_id')  # 👈 Get from form
    quantity = int(request.form.get('quantity', 1))  # Default to 1 if not provided

    product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
    if not product:
        flash("Product not found", "danger")
        return redirect(url_for('home'))

    cart_item = mongo.db.cart.find_one({'product_id': ObjectId(product_id)})

    if cart_item:
        mongo.db.cart.update_one({'_id': cart_item['_id']}, {'$inc': {'quantity': quantity}})
        flash("Quantity updated in the cart!", "success")
    else:
        mongo.db.cart.insert_one({
            
            'product_id': ObjectId(product_id),
            'quantity': quantity
        })
        flash("Product added to cart!", "success")

    return redirect(url_for('view_cart'))


@app.route('/remove-from-cart/<product_id>', methods=['POST'])
def remove_from_cart(product_id):
    # Find the cart item that matches the user and product_id
    cart_item = mongo.db.cart.find_one({'product_id': ObjectId(product_id)})
    
    if cart_item:
        # Remove the item from the cart
        mongo.db.cart.delete_one({'_id': cart_item['_id']})
        flash("Product removed from cart!", "success")
    else:
        flash("Product not found in cart!", "danger")

    # Redirect back to the cart page
    return redirect(url_for('view_cart'))



@app.route('/cart')
def view_cart():
    cart_items = list(mongo.db.cart.find())

    total = 0
    for item in cart_items:
        # Step 1: Get the product details from DB
        product = mongo.db.products.find_one({'_id': ObjectId(item['product_id'])})

        # Step 2: Add the product to the cart item
        item['product'] = product

        # Step 3: Calculate total
        total += product['price'] * item['quantity']

    # Step 4: Pass full cart_items to template
    return render_template('cart.html', cart_items=cart_items, total=total)



@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart_items = list(mongo.db.cart.find())
    if not cart_items:
        flash('Your cart is empty!', 'warning')
        return redirect(url_for('home'))

    if request.method == 'GET':
        return render_template('add_address.html')

    full_name = request.form['full_name']
    phone = request.form['phone']
    street = request.form['street']
    city = request.form['city']
    state = request.form['state']
    zip_code = request.form['zip_code']
    country = request.form['country']

    for item in cart_items:
        product = mongo.db.products.find_one({'_id': ObjectId(item['product_id'])})

        if product:
            order = {
                
                'product_id': ObjectId(item['product_id']),
                'quantity': item['quantity'],
                'order_date': datetime.now(),
                'status': 'Pending',
                'full_name': full_name,
                'phone': phone,
                'street': street,
                'city': city,
                'state': state,
                'zip_code': zip_code,
                'country': country,
                'product_name': product['name'],
                'product_price': product['price'],
            }

            mongo.db.orders.insert_one(order)

    mongo.db.cart.delete_many()

    return redirect(url_for('order_success'))



from bson.errors import InvalidId

@app.route('/product/<product_id>')
def product_detail(product_id):
    try:
        product = mongo.db.products.find_one({'_id': ObjectId(product_id)})
    except InvalidId:
        flash("Invalid product ID.", "danger")
        return redirect(url_for('home'))

    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for('home'))

    # Convert "image" to "images" so Jinja can access it
    if "image" in product and "images" not in product:
        product["images"] = product["image"]

    name = product['name'].strip().lower()

    if name == 'cardamom':
        return render_template('product1.html', product=product)
    elif name == 'pepper':
        return render_template('product2.html', product=product)
    elif name == 'mango pickle':
        return render_template('product3.html', product=product)
    elif name == 'meen achar':
        return render_template('product4.html', product=product)
    elif name == 'idiyirachi':
        return render_template('product5.html', product=product)
    elif name == 'payasam':
        return render_template('product6.html', product=product)
    elif name == 'chilly powder':
        return render_template('product7.html', product=product)
    elif name == 'pepper powder':
        return render_template('product8.html', product=product)
    elif name == 'lemon pickle':
        return render_template('product9.html', product=product)
    else:
        return render_template('product_generic.html', product=product)



@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/fix_order_ids')
def fix_order_ids():
    orders = mongo.db.orders.find()
    count = 0
    for order in orders:
        update_data = {}

        # Fix user_id if it's a string
        if 'user_id' in order and isinstance(order['user_id'], str):
            try:
                update_data['user_id'] = ObjectId(order['user_id'])
            except Exception as e:
                print(f"Skipping invalid user_id: {order['user_id']}")

        # Fix product_id if it's a string
        if 'product_id' in order and isinstance(order['product_id'], str):
            try:
                update_data['product_id'] = ObjectId(order['product_id'])
            except Exception as e:
                print(f"Skipping invalid product_id: {order['product_id']}")

        if update_data:
            mongo.db.orders.update_one({'_id': order['_id']}, {'$set': update_data})
            count += 1

    return f"Fixed {count} orders' IDs."

@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/login/google')
def login_google():
    redirect_uri = url_for('login_google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/login/callback')
def login_google_callback():
    token = google.authorize_access_token()
    resp = google.get('https://openidconnect.googleapis.com/v1/userinfo')
    user_info = resp.json()

    # Check if user exists in DB
    existing_user = mongo.db.users.find_one({'email': user_info['email']})
    if not existing_user:
        # Insert a new user (you can set default username / empty password / is_admin=False)
        user_id = mongo.db.users.insert_one({
            'username': user_info['name'],
            'email': user_info['email'],
            'password': '',  # No password for Google users
            'is_admin': False
        }).inserted_id
        user_data = mongo.db.users.find_one({'_id': user_id})
    else:
        user_data = existing_user

    # Log in the user using Flask-Login
    user = User(user_data)
    login_user(user)

    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)
