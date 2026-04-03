from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
from datetime import datetime, timedelta
import os
from docx import Document
from reportlab.pdfgen import canvas
from functools import wraps

app = Flask(__name__)
app.permanent_session_lifetime = timedelta(minutes=5)
app.secret_key = "secretkey"

# SQLite path
db_path = os.path.join(app.root_path, "booking.db")
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Admin credentials
ADMIN_USER = "Tanveer"
ADMIN_PASS = "998636"

# ---------------- DATABASE MODELS ----------------

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    model = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    location = db.Column(db.String(100))
    date = db.Column(db.DateTime, default=datetime.utcnow)

class Blog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)

class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    category = db.Column(db.String(50))
    price = db.Column(db.Integer)
    image = db.Column(db.String(200))
    badge = db.Column(db.String(50))

# ---------------- LOGIN REQUIRED ----------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash("Please login first")
            return redirect(url_for('admin'))
        return f(*args, **kwargs)
    return decorated_function

# ---------------- BOOKING PAGE ----------------

@app.route('/', methods=['GET', 'POST'])
def booking():
    if request.method == 'POST':
        selected_model = request.form.get('selected_model')
        if not selected_model:
            flash("Please select a vehicle to book.")
            return redirect(url_for('booking'))

        data = Booking(
            name=request.form['name'],
            model=selected_model,
            phone=request.form['phone'],
            location=request.form['location']
        )
        db.session.add(data)
        db.session.commit()
        flash("Booked Successfully! Our executive will call you soon")
        return redirect(url_for('booking'))

    blogs = Blog.query.all()

    banners = []
    banner_folder = os.path.join(app.static_folder, "images")
    if os.path.exists(banner_folder):
        banners = [f for f in os.listdir(banner_folder) if f.lower().endswith((".jpg", ".png", ".jpeg", ".webp"))]
        banners.sort()

    vehicles = Vehicle.query.all()
    # Category-wise vehicles safe handling
    scooters = [v for v in vehicles if v.category and v.category.lower() == 'scooter']
    motorcycles = [v for v in vehicles if v.category and v.category.lower() == 'motorcycle']
    electric = [v for v in vehicles if v.category and v.category.lower() == 'electric']

    return render_template(
        "booking.html",
        blogs=blogs,
        banners=banners,
        vehicles=vehicles,
        scooters=scooters,
        motorcycles=motorcycles,
        electric=electric
    )

# ---------------- ADMIN LOGIN ----------------

@app.route('/admin', methods=['GET','POST'])
def admin():
    if request.method == 'POST':
        if request.form['userid'] == ADMIN_USER and request.form['password'] == ADMIN_PASS:
            session.permanent = True
            session['admin_logged_in'] = True
            session['last_activity'] = datetime.utcnow().timestamp()
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid Credentials")
    return render_template("admin_login.html")

# ---------------- DASHBOARD ----------------

@app.route('/dashboard', methods=['GET','POST'])
@login_required
def dashboard():
    now = datetime.utcnow().timestamp()

    last_activity = session.get('last_activity')
    if last_activity and now - last_activity > 300:
        session.clear()
        flash("Session expired. Please login again.")
        return redirect(url_for('admin'))

    session['last_activity'] = now

    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = Booking.query
    if from_date and to_date:
        try:
            from_date_obj = datetime.strptime(from_date, "%Y-%m-%d")
            to_date_obj = datetime.strptime(to_date, "%Y-%m-%d")
            query = query.filter(Booking.date.between(from_date_obj, to_date_obj))
        except:
            flash("Invalid date format")

    bookings = query.all()
    blogs = Blog.query.all()
    vehicles = Vehicle.query.all()

    return render_template("admin_dashboard.html", bookings=bookings, blogs=blogs, vehicles=vehicles)

# ---------------- BLOG & VEHICLE ROUTES ----------------

@app.route('/add_blog', methods=['POST'])
@login_required
def add_blog():
    blog = Blog(title=request.form['title'], content=request.form['content'])
    db.session.add(blog)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/delete_blog/<int:id>')
@login_required
def delete_blog(id):
    blog = Blog.query.get(id)
    if blog:
        db.session.delete(blog)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/add_vehicle', methods=['POST'])
@login_required
def add_vehicle():
    name = request.form['name']
    category = request.form['category']
    price = int(request.form['price'])
    badge = request.form.get('badge') or None
    image_file = request.files.get('image')

    filename = None
    if image_file:
        filename = image_file.filename
        upload_path = os.path.join(app.static_folder, 'uploads')
        os.makedirs(upload_path, exist_ok=True)
        image_file.save(os.path.join(upload_path, filename))

    vehicle = Vehicle(name=name, category=category, price=price, image=filename, badge=badge)
    db.session.add(vehicle)
    db.session.commit()
    flash("Vehicle added successfully!")
    return redirect(url_for('dashboard'))

@app.route('/delete_vehicle/<int:id>')
@login_required
def delete_vehicle(id):
    vehicle = Vehicle.query.get(id)
    if vehicle:
        db.session.delete(vehicle)
        db.session.commit()
    flash("Vehicle deleted successfully!")
    return redirect(url_for('dashboard'))

# ---------------- EXPORT ----------------

@app.route('/export/<format>')
@login_required
def export(format):
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    query = Booking.query
    if from_date and to_date:
        try:
            from_date_obj = datetime.strptime(from_date, "%Y-%m-%d")
            to_date_obj = datetime.strptime(to_date, "%Y-%m-%d")
            query = query.filter(Booking.date.between(from_date_obj, to_date_obj))
        except:
            flash("Invalid date format")

    bookings = query.all()
    data = [[b.name, b.model, b.phone, b.location, b.date] for b in bookings]

    if format == "excel":
        file = "bookings.xlsx"
        pd.DataFrame(data, columns=["Name","Model","Phone","Location","Date"]).to_excel(file, index=False)
        return send_file(file, as_attachment=True)

    if format == "word":
        file = "bookings.docx"
        doc = Document()
        doc.add_heading("Booking List")
        for row in data:
            doc.add_paragraph(str(row))
        doc.save(file)
        return send_file(file, as_attachment=True)

    if format == "pdf":
        file = "bookings.pdf"
        c = canvas.Canvas(file)
        y = 800
        for row in data:
            c.drawString(30, y, str(row))
            y -= 20
        c.save()
        return send_file(file, as_attachment=True)

# ---------------- LOGOUT ----------------

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash("Logged out successfully")
    return redirect(url_for('admin'))

# ---------------- CREATE TABLES ----------------

with app.app_context():
    db.create_all()

# ---------------- RUN ----------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)