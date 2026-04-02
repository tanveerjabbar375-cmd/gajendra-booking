from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import os
import time
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'secret123'

# 🔥 Upload folder
UPLOAD_FOLDER = 'static/images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 🔥 DB connection helper
def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# 🔥 Create tables (auto)
def create_tables():
    conn = get_db()
    c = conn.cursor()

    # bookings
    c.execute('''
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        location TEXT,
        model TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # vehicles
    c.execute('''
    CREATE TABLE IF NOT EXISTS vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price TEXT,
        type TEXT,
        image1 TEXT
    )
    ''')

    # blogs
    c.execute('''
    CREATE TABLE IF NOT EXISTS blogs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        content TEXT
    )
    ''')

    conn.commit()
    conn.close()

create_tables()

# 🔥 HOME / BOOKING PAGE
@app.route('/', methods=['GET', 'POST'])
def booking():
    conn = get_db()
    c = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        location = request.form['location']
        model = request.form['model']

        c.execute("INSERT INTO bookings (name, phone, location, model) VALUES (?,?,?,?)",
                  (name, phone, location, model))
        conn.commit()
        flash("Booking Successful! Our executive will call you soon.")

    vehicles = c.execute("SELECT * FROM vehicles").fetchall()
    blogs = c.execute("SELECT * FROM blogs").fetchall()

    conn.close()

    banners = []  # optional (unchanged)
    return render_template('booking.html', vehicles=vehicles, blogs=blogs, banners=banners)


# 🔥 ADMIN DASHBOARD
@app.route('/dashboard')
def dashboard():
    conn = get_db()
    c = conn.cursor()

    bookings = c.execute("SELECT * FROM bookings ORDER BY id DESC").fetchall()
    vehicles = c.execute("SELECT * FROM vehicles ORDER BY id DESC").fetchall()
    blogs = c.execute("SELECT * FROM blogs").fetchall()

    conn.close()

    return render_template('admin_dashboard.html',
                           bookings=bookings,
                           vehicles=vehicles,
                           blogs=blogs)


# 🔥 ADD VEHICLE (AUTO IMAGE UPLOAD)
@app.route('/add_vehicle', methods=['POST'])
def add_vehicle():
    name = request.form['name']
    price = request.form['price']
    type_ = request.form['type']

    image = request.files['image1']

    if image:
        filename = str(int(time.time())) + "_" + secure_filename(image.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(image_path)
    else:
        filename = ""

    conn = get_db()
    c = conn.cursor()

    c.execute("INSERT INTO vehicles (name, price, type, image1) VALUES (?,?,?,?)",
              (name, price, type_, filename))

    conn.commit()
    conn.close()

    return redirect('/dashboard')


# 🔥 DELETE VEHICLE
@app.route('/delete_vehicle/<int:id>')
def delete_vehicle(id):
    conn = get_db()
    c = conn.cursor()

    c.execute("DELETE FROM vehicles WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect('/dashboard')


# 🔥 ADD BLOG
@app.route('/add_blog', methods=['POST'])
def add_blog():
    title = request.form['title']
    content = request.form['content']

    conn = get_db()
    c = conn.cursor()

    c.execute("INSERT INTO blogs (title, content) VALUES (?,?)",
              (title, content))

    conn.commit()
    conn.close()

    return redirect('/dashboard')


# 🔥 DELETE BLOG
@app.route('/delete_blog/<int:id>')
def delete_blog(id):
    conn = get_db()
    c = conn.cursor()

    c.execute("DELETE FROM blogs WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect('/dashboard')


# 🔥 RUN APP (LOCAL ONLY)
if __name__ == "__main__":
    app.run(debug=True)