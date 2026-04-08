from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session, abort
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

# ---------------- POSTGRES CONFIG ----------------
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://gajendra_user:AEfojPqfRefvTI4iLU7HCQq9ans0Fv1@dpg-d781aaudqaus73bff770-a/gajendra_db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------------- ADMIN CREDENTIALS ----------------
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

    @staticmethod
    def analytics_by_month():
        # Placeholder for chart data (month: bookings count)
        return {"Jan": 5, "Feb": 7, "Mar": 10}  # Example

class Blog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    image = db.Column(db.String(200))
    alt_text = db.Column(db.String(200))
    views = db.Column(db.Integer, default=0)

    @staticmethod
    def analytics_views():
        # Placeholder for chart data (blog title: views)
        blogs = Blog.query.all()
        return {b.title: b.views for b in blogs}

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
    vehicles = Vehicle.query.all()

    scooters = [v for v in vehicles if v.category and v.category.lower() == 'scooter']
    motorcycles = [v for v in vehicles if v.category and v.category.lower() == 'motorcycle']
    electric = [v for v in vehicles if v.category and v.category.lower() == 'electric']

    banners = []
    banner_folder = os.path.join(app.static_folder, "images")
    if os.path.exists(banner_folder):
        banners = [f for f in os.listdir(banner_folder) if f.lower().endswith((".jpg", ".png", ".jpeg", ".webp"))]
        banners.sort()

    return render_template(
        "booking.html",
        blogs=blogs,
        banners=banners,
        vehicles=vehicles,
        scooters=scooters,
        motorcycles=motorcycles,
        electric=electric
    )

# ---------------- BLOG OPEN PAGE ----------------

@app.route('/blog/<int:id>')
def blog_open(id):
    blog = Blog.query.get_or_404(id)
    blog.views += 1
    db.session.commit()
    return render_template("blog_page.html", blog=blog)

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

    # Analytics
    booking_counts = Booking.analytics_by_month()
    blog_views = Blog.analytics_views()

    return render_template(
        "admin_dashboard.html",
        bookings=bookings,
        blogs=blogs,
        vehicles=vehicles,
        booking_counts=booking_counts,
        blog_views=blog_views
    )

# ---------------- BLOG ROUTES ----------------

@app.route('/add_blog', methods=['POST'])
@login_required
def add_blog():
    image_file = request.files.get('image')
    filename = None

    if image_file and image_file.filename:
        filename = image_file.filename
        upload_path = os.path.join(app.static_folder, 'uploads')
        os.makedirs(upload_path, exist_ok=True)
        image_file.save(os.path.join(upload_path, filename))

    blog = Blog(
        title=request.form['title'],
        content=request.form['content'],
        image=filename,
        alt_text=request.form.get('alt_text')
    )

    db.session.add(blog)
    db.session.commit()
    flash("Blog added successfully!")
    return redirect(url_for('dashboard'))

@app.route('/edit_blog/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_blog(id):
    blog = Blog.query.get_or_404(id)

    if request.method == 'POST':
        blog.title = request.form['title']
        blog.content = request.form['content']
        blog.alt_text = request.form.get('alt_text')

        image_file = request.files.get('image')
        if image_file and image_file.filename:
            filename = image_file.filename
            upload_path = os.path.join(app.static_folder, 'uploads')
            os.makedirs(upload_path, exist_ok=True)
            image_file.save(os.path.join(upload_path, filename))
            blog.image = filename

        db.session.commit()
        flash("Blog updated successfully!")
        return redirect(url_for('dashboard'))

    return render_template('edit_blog.html', blog=blog)

@app.route('/delete_blog/<int:id>')
@login_required
def delete_blog(id):
    blog = Blog.query.get(id)
    if blog:
        db.session.delete(blog)
        db.session.commit()
        flash("Blog deleted successfully!")
    return redirect(url_for('dashboard'))

# ---------------- VEHICLE ROUTES ----------------

@app.route('/add_vehicle', methods=['POST'])
@login_required
def add_vehicle():
    name = request.form['name']
    category = request.form['category']
    price = int(request.form['price'])
    badge = request.form.get('badge') or None
    image_file = request.files.get('image')

    filename = None
    if image_file and image_file.filename:
        filename = image_file.filename
        upload_path = os.path.join(app.static_folder, 'uploads')
        os.makedirs(upload_path, exist_ok=True)
        image_file.save(os.path.join(upload_path, filename))

    vehicle = Vehicle(name=name, category=category, price=price, image=filename, badge=badge)
    db.session.add(vehicle)
    db.session.commit()
    flash("Vehicle added successfully!")
    return redirect(url_for('dashboard'))

@app.route('/edit_vehicle/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_vehicle(id):
    vehicle = Vehicle.query.get_or_404(id)

    if request.method == 'POST':
        vehicle.name = request.form['name']
        vehicle.category = request.form['category']
        vehicle.price = int(request.form['price'])
        vehicle.badge = request.form.get('badge')

        image_file = request.files.get('image')
        if image_file and image_file.filename:
            filename = image_file.filename
            upload_path = os.path.join(app.static_folder, 'uploads')
            os.makedirs(upload_path, exist_ok=True)
            image_file.save(os.path.join(upload_path, filename))
            vehicle.image = filename

        db.session.commit()
        flash("Vehicle updated successfully!")
        return redirect(url_for('dashboard'))

    return render_template('edit_vehicle.html', vehicle=vehicle)

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
    data = [[b.name, b.model, b.phone, b.location, b.date.strftime("%Y-%m-%d %H:%M")] for b in bookings]

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

# ---------------- PING ----------------
@app.route("/ping")
def ping():
    return "alive", 200

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