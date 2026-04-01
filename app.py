from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = "secretkey"
app.permanent_session_lifetime = timedelta(minutes=5)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///booking.db'
db = SQLAlchemy(app)

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
    badge = db.Column(db.String(50))

class VehicleImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'))
    filename = db.Column(db.String(200))
    vehicle = db.relationship('Vehicle', backref=db.backref('images', lazy=True))

# ---------------- LOGIN DECORATOR ----------------
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

        booking = Booking(
            name=request.form['name'],
            model=selected_model,
            phone=request.form['phone'],
            location=request.form['location']
        )
        db.session.add(booking)
        db.session.commit()
        flash("Booked Successfully! Our executive will call you soon")
        return redirect(url_for('booking'))

    blogs = Blog.query.all()
    vehicles = Vehicle.query.all()
    banner_folder = os.path.join(app.static_folder, "images")
    banners = [f for f in os.listdir(banner_folder) if f.lower().endswith((".jpg",".png",".jpeg",".webp"))]
    banners.sort()

    return render_template("booking.html", blogs=blogs, banners=banners, vehicles=vehicles)

# ---------------- ADMIN LOGIN ----------------
ADMIN_USER = "Tanveer"
ADMIN_PASS = "998636"

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
    if 'last_activity' in session and now - session['last_activity'] > 300:
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
    vehicles = Vehicle.query.all()
    return render_template("admin_dashboard.html", bookings=bookings, blogs=blogs, vehicles=vehicles)

# ---------------- VEHICLE ADD ----------------
@app.route('/add_vehicle', methods=['POST'])
@login_required
def add_vehicle():
    name = request.form['name']
    category = request.form['category']
    price = int(request.form['price'])
    badge = request.form.get('badge') or None
    image_files = request.files.getlist('images')  # get multiple images

    vehicle = Vehicle(name=name, category=category, price=price, badge=badge)
    db.session.add(vehicle)
    db.session.commit()  # commit to get vehicle.id

    upload_path = os.path.join(app.static_folder, 'uploads')
    os.makedirs(upload_path, exist_ok=True)

    for image_file in image_files:
        if image_file:
            filename = f"{vehicle.id}_{image_file.filename}"
            image_file.save(os.path.join(upload_path, filename))
            # Save each image in VehicleImage table
            img = VehicleImage(vehicle_id=vehicle.id, filename=filename)
            db.session.add(img)

    db.session.commit()
    flash("Vehicle added successfully!")
    return redirect(url_for('dashboard'))

@app.route('/delete_vehicle/<int:id>')
@login_required
def delete_vehicle(id):
    vehicle = Vehicle.query.get(id)
    if vehicle:
        for img in vehicle.images:
            try:
                os.remove(os.path.join(app.static_folder, 'uploads', img.filename))
            except:
                pass
        db.session.delete(vehicle)
        db.session.commit()
    flash("Vehicle deleted successfully!")
    return redirect(url_for('dashboard'))

# ---------------- LOGOUT ----------------
@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash("Logged out successfully")
    return redirect(url_for('admin'))

# ---------------- RUN ----------------
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)