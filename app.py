from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta
from functools import wraps
from sqlalchemy import func
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os
import pandas as pd
from docx import Document
from reportlab.pdfgen import canvas

# ---------------- LOAD ENV ----------------
load_dotenv()

app = Flask(__name__)
app.permanent_session_lifetime = timedelta(minutes=5)

# ---------------- SECRET KEY ----------------
app.secret_key = os.getenv("SECRET_KEY", "secretkey")

# ---------------- DATABASE CONFIG ----------------
uri = os.getenv("DATABASE_URL")

# Render fix (IMPORTANT)
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ---------------- INIT DB ----------------
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# ---------------- UPLOAD FOLDER ----------------
UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------- ADMIN ----------------
ADMIN_USER = "Tanveer"
ADMIN_PASS = "998636"

# ---------------- MODELS ----------------
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
    image = db.Column(db.String(200))   # NEW FIELD


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
    def wrapper(*args, **kwargs):
        if "admin_logged_in" not in session:
            flash("Please login first")
            return redirect(url_for("admin"))
        return f(*args, **kwargs)
    return wrapper

# ---------------- BOOKING PAGE ----------------
@app.route("/", methods=["GET", "POST"])
def booking():
    if request.method == "POST":
        selected_model = request.form.get("selected_model")

        if not selected_model:
            flash("Please select a vehicle to book.")
            return redirect(url_for("booking"))

        booking = Booking(
            name=request.form["name"],
            model=selected_model,
            phone=request.form["phone"],
            location=request.form["location"]
        )

        db.session.add(booking)
        db.session.commit()

        flash("Booked Successfully! Our executive will call you soon")
        return redirect(url_for("booking"))

    blogs = Blog.query.all()
    vehicles = Vehicle.query.all()

    scooters = [v for v in vehicles if v.category and v.category.lower() == "scooter"]
    motorcycles = [v for v in vehicles if v.category and v.category.lower() == "motorcycle"]
    electric = [v for v in vehicles if v.category and v.category.lower() == "electric"]

    return render_template(
        "booking.html",
        blogs=blogs,
        vehicles=vehicles,
        scooters=scooters,
        motorcycles=motorcycles,
        electric=electric
    )

# ---------------- BLOG VIEW ----------------
@app.route("/blog/<int:id>")
def view_blog(id):
    blog = Blog.query.get_or_404(id)
    return render_template("blog_view.html", blog=blog)

# ---------------- ADMIN LOGIN ----------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form["userid"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            session["admin_logged_in"] = True
            session["last_activity"] = datetime.utcnow().timestamp()
            return redirect(url_for("dashboard"))
        flash("Invalid Credentials")
    return render_template("admin_login.html")

# ---------------- DASHBOARD + ANALYTICS ----------------
@app.route("/dashboard")
@login_required
def dashboard():

    # session timeout
    now = datetime.utcnow().timestamp()
    last = session.get("last_activity")

    if last and now - last > 300:
        session.clear()
        flash("Session expired")
        return redirect(url_for("admin"))

    session["last_activity"] = now

    bookings = Booking.query.all()
    blogs = Blog.query.all()
    vehicles = Vehicle.query.all()

    total_bookings = Booking.query.count()

    last_7_days = datetime.utcnow() - timedelta(days=7)

    bookings_per_day = db.session.query(
        func.date(Booking.date),
        func.count(Booking.id)
    ).filter(Booking.date >= last_7_days)\
     .group_by(func.date(Booking.date)).all()

    dates = [str(x[0]) for x in bookings_per_day]
    counts = [x[1] for x in bookings_per_day]

    top_vehicles = db.session.query(
        Booking.model,
        func.count(Booking.id)
    ).group_by(Booking.model)\
     .order_by(func.count(Booking.id).desc()).limit(5).all()

    locations = db.session.query(
        Booking.location,
        func.count(Booking.id)
    ).group_by(Booking.location).all()

    return render_template(
        "admin_dashboard.html",
        bookings=bookings,
        blogs=blogs,
        vehicles=vehicles,
        total_bookings=total_bookings,
        dates=dates,
        counts=counts,
        top_vehicles=top_vehicles,
        locations=locations
    )

# ---------------- ADD BLOG ----------------
@app.route("/add_blog", methods=["POST"])
@login_required
def add_blog():

    file = request.files.get("image")
    filename = None

    if file and file.filename:
        filename = secure_filename(file.filename)
        file.save(os.path.join(UPLOAD_FOLDER, filename))

    blog = Blog(
        title=request.form["title"],
        content=request.form["content"],
        image=filename
    )

    db.session.add(blog)
    db.session.commit()

    flash("Blog added successfully")
    return redirect(url_for("dashboard"))

# ---------------- DELETE BLOG ----------------
@app.route("/delete_blog/<int:id>")
@login_required
def delete_blog(id):
    blog = Blog.query.get(id)
    if blog:
        db.session.delete(blog)
        db.session.commit()
    return redirect(url_for("dashboard"))

# ---------------- VEHICLES ----------------
@app.route("/add_vehicle", methods=["POST"])
@login_required
def add_vehicle():

    file = request.files.get("image")
    filename = None

    if file and file.filename:
        filename = secure_filename(file.filename)
        file.save(os.path.join(UPLOAD_FOLDER, filename))

    vehicle = Vehicle(
        name=request.form["name"],
        category=request.form["category"],
        price=int(request.form["price"]),
        badge=request.form.get("badge"),
        image=filename
    )

    db.session.add(vehicle)
    db.session.commit()

    return redirect(url_for("dashboard"))

# ---------------- EDIT VEHICLE ----------------
@app.route("/edit_vehicle/<int:id>", methods=["GET", "POST"])
@login_required
def edit_vehicle(id):
    vehicle = Vehicle.query.get_or_404(id)

    if request.method == "POST":
        vehicle.name = request.form["name"]
        vehicle.category = request.form["category"]
        vehicle.price = int(request.form["price"])
        vehicle.badge = request.form.get("badge")

        file = request.files.get("image")
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            vehicle.image = filename

        db.session.commit()
        flash("Vehicle updated successfully")
        return redirect(url_for("dashboard"))

    return render_template("edit_vehicle.html", vehicle=vehicle)

@app.route("/delete_vehicle/<int:id>")
@login_required
def delete_vehicle(id):
    vehicle = Vehicle.query.get_or_404(id)
    db.session.delete(vehicle)
    db.session.commit()
    flash("Vehicle deleted")
    return redirect(url_for("dashboard"))

# ---------------- LOGOUT ----------------
@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("admin"))

# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)