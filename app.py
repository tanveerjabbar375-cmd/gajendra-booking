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
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///booking.db'
db = SQLAlchemy(app)

# Default Admin Credentials
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

class Vehicle(db.Model):  # New model for vehicles with images, price, category etc
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    category = db.Column(db.String(50))  # e.g., 'Scooter', 'Motorcycle', 'Electric'
    price = db.Column(db.Integer)        # price per day
    image = db.Column(db.String(200))   # filename of vehicle image stored in static/uploads/
    badge = db.Column(db.String(50))    # e.g., 'Most Popular', 'Limited Offer' or None

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
        flash("Booked Successfully!")
        return redirect(url_for('booking'))

    # Blogs fetch
    blogs = Blog.query.all()

    # Dynamic banners from static/images folder
    banner_folder = os.path.join(app.static_folder, "images")
    banners = [f for f in os.listdir(banner_folder) if f.lower().endswith((".jpg", ".png", ".jpeg", ".webp"))]
    banners.sort()  # optional: alphabetically

    # Vehicles fetch for booking page
    vehicles = Vehicle.query.all()

    return render_template("booking.html", blogs=blogs, banners=banners, vehicles=vehicles)

# ---------------- ADMIN LOGIN ----------------

@app.route('/admin', methods=['GET','POST'])
def admin():
    global ADMIN_USER, ADMIN_PASS
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

    if 'last_activity' in session:
        if now - session['last_activity'] > 300:
            session.clear()
            flash("Session expired. Please login again.")
            return redirect(url_for('admin'))

    session['last_activity'] = now

    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = Booking.query

    if from_date and to_date:
        from_date_obj = datetime.strptime(from_date, "%Y-%m-%d")
        to_date_obj = datetime.strptime(to_date, "%Y-%m-%d")
        query = query.filter(Booking.date.between(from_date_obj, to_date_obj))

    bookings = query.all()
    blogs = Blog.query.all()
    vehicles = Vehicle.query.all()  # for admin management

    return render_template("admin_dashboard.html",
                           bookings=bookings,
                           blogs=blogs,
                           vehicles=vehicles)

# ---------------- BLOG ADD ----------------

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

# ---------------- VEHICLE ADD ----------------

@app.route('/add_vehicle', methods=['POST'])
@login_required
def add_vehicle():
    name = request.form['name']
    category = request.form['category']
    price = int(request.form['price'])
    badge = request.form.get('badge') or None
    image_file = request.files.get('image')

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
        # Optionally delete image file too (not implemented)
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
        from_date_obj = datetime.strptime(from_date, "%Y-%m-%d")
        to_date_obj = datetime.strptime(to_date, "%Y-%m-%d")
        query = query.filter(Booking.date.between(from_date_obj, to_date_obj))

    bookings = query.all()

    data = []
    for b in bookings:
        data.append([b.name, b.model, b.phone, b.location, b.date])

    df = pd.DataFrame(data, columns=["Name","Model","Phone","Location","Date"])

    if format == "excel":
        file = "bookings.xlsx"
        df.to_excel(file, index=False)
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
            c.drawString(30,y,str(row))
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

# ---------------- RUN ----------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)