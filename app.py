from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from functools import wraps
import os
import pandas as pd
from docx import Document
from reportlab.pdfgen import canvas
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "secretkey"
app.permanent_session_lifetime = timedelta(minutes=5)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///booking.db'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'vehicle_images')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# ---------------- ADMIN ----------------
ADMIN_USER = "Tanveer"
ADMIN_PASS = "998636"

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash("Please login first")
            return redirect(url_for('admin'))
        return f(*args, **kwargs)
    return decorated

# ---------------- DATABASE ----------------

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'))
    name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    location = db.Column(db.String(100))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    vehicle = db.relationship("Vehicle")

class Blog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)

class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_type = db.Column(db.String(10))  # MC / SC / EV
    model = db.Column(db.String(100))
    price = db.Column(db.Float)
    font_color = db.Column(db.String(20))
    images = db.relationship('VehicleImage', backref='vehicle', cascade="all, delete-orphan")

class VehicleImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'))

# ---------------- ROUTES ----------------

@app.route('/', methods=['GET', 'POST'])
def booking():
    vehicles = Vehicle.query.all()
    @app.route('/', methods=['GET', 'POST'])
def booking():
    if request.method == 'POST':
        vehicle_id = request.form['vehicle_id']
        vehicle = Vehicle.query.get(vehicle_id)
        data = Booking(
            name=request.form['name'],
            model=vehicle.model,
            phone=request.form['phone'],
            location=request.form['location']
        )
        db.session.add(data)
        db.session.commit()
        flash("Booked Successfully!")
        return redirect(url_for('booking'))

    vehicles = Vehicle.query.all()
    blogs = Blog.query.all()
    return render_template("booking.html", vehicles=vehicles, blogs=blogs)
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
    # Auto logout after inactivity
    now = datetime.utcnow().timestamp()
    if 'last_activity' in session:
        if now - session['last_activity'] > 300:
            session.clear()
            flash("Session expired. Please login again.")
            return redirect(url_for('admin'))
    session['last_activity'] = now

    # Filters
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = Booking.query
    if from_date and to_date:
        from_obj = datetime.strptime(from_date, "%Y-%m-%d")
        to_obj = datetime.strptime(to_date, "%Y-%m-%d")
        query = query.filter(Booking.date.between(from_obj, to_obj))

    bookings = query.all()
    blogs = Blog.query.all()
    vehicles = Vehicle.query.all()
    return render_template("admin_dashboard.html", bookings=bookings, blogs=blogs, vehicles=vehicles)

# ---------------- BLOG ROUTES ----------------
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
    db.session.delete(blog)
    db.session.commit()
    return redirect(url_for('dashboard'))

# ---------------- VEHICLE MANAGEMENT ----------------
@app.route('/add_vehicle', methods=['POST'])
@login_required
def add_vehicle():
    vehicle_type = request.form.get('vehicle_type')
    model = request.form.get('model')
    price = request.form.get('price')
    font_color = request.form.get('font_color', '#000000')
    images_files = request.files.getlist('images')

    vehicle = Vehicle(vehicle_type=vehicle_type, model=model, price=float(price), font_color=font_color)
    db.session.add(vehicle)
    db.session.commit()

    for img in images_files:
        if img.filename:
            filename = f"{vehicle.id}_{secure_filename(img.filename)}"
            img.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            v_img = VehicleImage(vehicle_id=vehicle.id, filename=filename)
            db.session.add(v_img)
    db.session.commit()
    flash("Vehicle added successfully")
    return redirect(url_for('dashboard'))

@app.route('/delete_vehicle/<int:id>')
@login_required
def delete_vehicle(id):
    vehicle = Vehicle.query.get(id)
    db.session.delete(vehicle)
    db.session.commit()
    flash("Vehicle deleted successfully")
    return redirect(url_for('dashboard'))

# ---------------- EXPORT ----------------
@app.route('/export/<format>')
def export(format):
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    query = Booking.query
    if from_date and to_date:
        from_obj = datetime.strptime(from_date, "%Y-%m-%d")
        to_obj = datetime.strptime(to_date, "%Y-%m-%d")
        query = query.filter(Booking.date.between(from_obj, to_obj))

    bookings = query.all()
    data = [[b.name, b.vehicle.model if b.vehicle else "", b.vehicle.price if b.vehicle else "", b.phone, b.location, b.date] for b in bookings]
    df = pd.DataFrame(data, columns=["Name","Vehicle","Price","Phone","Location","Date"])

    if format=="excel":
        file="bookings.xlsx"
        df.to_excel(file,index=False)
        return send_file(file, as_attachment=True)
    if format=="word":
        file="bookings.docx"
        doc = Document()
        doc.add_heading("Booking List")
        for row in data:
            doc.add_paragraph(str(row))
        doc.save(file)
        return send_file(file, as_attachment=True)
    if format=="pdf":
        file="bookings.pdf"
        c = canvas.Canvas(file)
        y=800
        for row in data:
            c.drawString(30,y,str(row))
            y-=20
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