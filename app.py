from flask import (
    Flask, render_template, request, jsonify, session, redirect,
    send_from_directory, url_for
)
import random
from email.mime.text import MIMEText
import smtplib
from datetime import datetime, timedelta
import mysql.connector
import os
from werkzeug.utils import secure_filename
from config import *
from threading import Thread
import time


# -----------------------
# Flask + Upload Folders
# -----------------------
app = Flask(__name__)
app.secret_key = SECRET_KEY

BASE_UPLOAD = os.path.join(os.getcwd(), "uploads")
OFFER_FOLDER = os.path.join(BASE_UPLOAD, "offers")
PHOTO_FOLDER = os.path.join(BASE_UPLOAD, "photos")

os.makedirs(OFFER_FOLDER, exist_ok=True)
os.makedirs(PHOTO_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf"}


# -----------------------
# Database Helper
# -----------------------
def get_db():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )


# -----------------------
# Email Helper
# -----------------------
def send_email(to, subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = MAIL_USERNAME
        msg["To"] = to

        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
            server.starttls()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.sendmail(MAIL_USERNAME, [to], msg.as_string())

    except Exception as e:
        print("Email send error:", e)


# -----------------------
# Utility Helpers
# -----------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def fetch_student_by_email(email):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM students WHERE email=%s", (email,))
    student = cur.fetchone()
    cur.close()
    db.close()
    return student


# -----------------------
# OTP ROUTES
# -----------------------
@app.route("/send_otp", methods=["POST"])
@app.route("/send-otp", methods=["POST"])
def send_otp():
    email = request.form.get("email")

    if not email or not email.endswith(ALLOWED_DOMAIN):
        return jsonify({"status": "error", "message": f"Only {ALLOWED_DOMAIN} emails allowed"}), 400

    otp = str(random.randint(100000, 999999))

    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO otps (email, otp, timestamp) VALUES (%s, %s, %s)",
        (email, otp, datetime.now())
    )
    db.commit()
    cur.close()
    db.close()

    send_email(email, "Your Login OTP", f"Your OTP is: {otp}\nValid for {OTP_EXPIRY_MINUTES} minutes.")

    session["email"] = email
    return jsonify({"status": "success", "message": "OTP sent"})


@app.route("/verify_otp", methods=["POST"])
@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    email = session.get("email")
    otp_entered = request.form.get("otp")

    if not email:
        return jsonify({"status": "error", "message": "Session expired"}), 400

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM otps WHERE email=%s ORDER BY id DESC LIMIT 1", (email,))
    record = cur.fetchone()
    cur.close()
    db.close()

    if not record:
        return jsonify({"status": "error", "message": "No OTP found"}), 400

    if datetime.now() > record["timestamp"] + timedelta(minutes=OTP_EXPIRY_MINUTES):
        return jsonify({"status": "error", "message": "OTP expired"}), 400

    if otp_entered != record["otp"]:
        return jsonify({"status": "error", "message": "Incorrect OTP"}), 400

    # Verified
    session["email"] = email

    student = fetch_student_by_email(email)
    if not student:
        return jsonify({"status": "new_user", "redirect": url_for("student_form")})

    return jsonify({"status": "success", "redirect": url_for("student_dashboard")})


# -----------------------
# ADD / UPDATE STUDENT
# -----------------------
@app.route("/add_student", methods=["POST"])
def add_student():
    email = request.form.get("email") or session.get("email")

    if not email:
        return jsonify({"status": "error", "message": "No email provided"}), 400

    name = request.form.get("name", "").strip()
    roll_no = request.form.get("roll_no", "").strip()
    personal_email = request.form.get("personal_email", "").strip()
    contact = request.form.get("contact", "").strip()
    company = request.form.get("company", "").strip()
    city = request.form.get("city", "").strip()
    stipend = request.form.get("stipend", "").strip()
    role_offered = (request.form.get("role_offered") or request.form.get("role") or "").strip()
    joining_date = request.form.get("joining_date", "").strip() or None
    address = request.form.get("address", "").strip()
    status = (request.form.get("status") or "Not Placed").strip()

    # ---- Backend validation (all key fields required) ----
    required_fields = [
        name, roll_no, personal_email, contact,
        company, city, stipend, role_offered, address
    ]

    if any(f == "" for f in required_fields):
        return jsonify({"status": "error", "message": "All fields are required"}), 400

    # contact must be 10 digits
    if not contact.isdigit() or len(contact) != 10:
        return jsonify({"status": "error", "message": "Contact must be a 10-digit number"}), 400

    # stipend should be numeric (simple check)
    if not stipend.replace(",", "").replace("_", "").replace(" ", "").isdigit():
        return jsonify({"status": "error", "message": "Stipend must be a number (you can add commas)"}), 400

    # Photo Upload
    photo_file = request.files.get("photo")
    photo_filename = None

    if photo_file and photo_file.filename:
        ext = photo_file.filename.rsplit(".", 1)[1]
        photo_filename = secure_filename(f"{roll_no}_photo.{ext}")
        photo_path = os.path.join(PHOTO_FOLDER, photo_filename)
        photo_file.save(photo_path)

    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT id FROM students WHERE email=%s", (email,))
    exists = cur.fetchone()

    if exists:
        cur.execute(
            """
            UPDATE students SET
                name=%s,
                roll_no=%s,
                personal_email=%s,
                contact=%s,
                company=%s,
                city=%s,
                stipend=%s,
                role_offered=%s,
                joining_date=%s,
                address=%s,
                status=%s,
                photo_filename=COALESCE(%s, photo_filename)
            WHERE email=%s
            """,
            (
                name, roll_no, personal_email, contact, company, city,
                stipend, role_offered, joining_date, address,
                status, photo_filename, email
            )
        )
    else:
        cur.execute(
            """
            INSERT INTO students
                (name,email,roll_no,personal_email,contact,company,city,stipend,
                 role_offered,joining_date,address,status,photo_filename)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                name, email, roll_no, personal_email, contact, company,
                city, stipend, role_offered, joining_date, address,
                status, photo_filename
            )
        )

    db.commit()
    cur.close()
    db.close()

    return jsonify({"status": "success"})


# -----------------------
# Offer Upload (Redirect + AJAX)
# -----------------------
@app.route("/upload_offer", methods=["POST"])
def upload_offer():
    email = request.form.get("email") or session.get("email")

    if not email:
        return jsonify({"status": "error", "message": "No email provided"}), 400

    file = request.files.get("offer_letter") or request.files.get("offer")

    if not file or not file.filename:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400

    if not allowed_file(file.filename):
        return jsonify({"status": "error", "message": "Only PDF allowed"}), 400

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT roll_no, name FROM students WHERE email=%s", (email,))
    st = cur.fetchone()

    # Create student if missing
    if not st:
        fallback_roll = email.split("@")[0]
        cur2 = db.cursor()
        cur2.execute(
            """
            INSERT INTO students (name,email,roll_no,status)
            VALUES (%s,%s,%s,%s)
            """,
            ("", email, fallback_roll, "Not Placed")
        )
        db.commit()
        cur2.close()

        cur.execute("SELECT roll_no,name FROM students WHERE email=%s", (email,))
        st = cur.fetchone()

    roll = (st.get("roll_no") or email.split("@")[0]).strip()
    name = (st.get("name") or "").strip().replace(" ", "_") or email.split("@")[0]

    filename = secure_filename(f"{roll}_{name}.pdf")
    filepath = os.path.join(OFFER_FOLDER, filename)
    file.save(filepath)

    cur.execute(
        "UPDATE students SET offer_filename=%s, status='Placed' WHERE email=%s",
        (filename, email)
    )
    db.commit()
    cur.close()
    db.close()

    # If AJAX
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"status": "success", "filename": filename})

    # Normal form → redirect to thank_you page
    return redirect(url_for("thank_you"))


# alias
@app.route("/upload_offer_letter", methods=["POST"])
def upload_offer_letter_post():
    return upload_offer()


@app.route("/upload_offer_letter", methods=["GET"])
def upload_offer_letter_page():
    email = session.get("email")
    if not email:
        return redirect("/login")
    student = fetch_student_by_email(email)
    return render_template("upload_offer_letter.html", student=student)


# -----------------------
# THANK YOU PAGE
# -----------------------
@app.route("/thank_you")
def thank_you():
    return render_template("thank_you.html")



# -----------------------
# Download Offer
# -----------------------
@app.route("/download_offer/<filename>")
def download_offer(filename):
    return send_from_directory(OFFER_FOLDER, filename, as_attachment=True)


# -----------------------
# Filter Students
# -----------------------
@app.route("/filter_students", methods=["GET"])
def filter_students():
    status = request.args.get("status")

    db = get_db()
    cur = db.cursor(dictionary=True)

    if status == "placed":
        cur.execute("SELECT * FROM students WHERE status='Placed'")
    elif status == "not_placed":
        cur.execute("SELECT * FROM students WHERE status='Not Placed'")
    else:
        cur.execute("SELECT * FROM students")

    rows = cur.fetchall()
    cur.close()
    db.close()
    return jsonify(rows)


# -----------------------
# Teacher Login PAGE (GET)
# -----------------------
@app.route("/teacher_login_page")
def teacher_login_page():
    return render_template("teacher_login.html")


# -----------------------
# Logout (for both student & teacher)
# -----------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# -----------------------
# Pages
# -----------------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login")
def login_page():
    return render_template("login.html")


@app.route("/student_form")
def student_form():
    email = session.get("email")
    if not email:
        return redirect("/login")
    student = fetch_student_by_email(email)
    return render_template("student_form.html", student=student)


@app.route("/student_dashboard")
def student_dashboard():
    email = session.get("email")
    if not email:
        return redirect("/login")
    student = fetch_student_by_email(email)
    return render_template("student_dashboard.html", student=student)


@app.route("/teacher_dashboard")
def teacher_dashboard():
    if "teacher" not in session:
        return redirect("/teacher_login_page")
    db = get_db()
    cur = db.cursor(dictionary=True)
    # No last_updated column needed; order by roll number for clarity
    cur.execute("SELECT * FROM students ORDER BY roll_no")
    students = cur.fetchall()
    cur.close()
    db.close()
    return render_template("teacher_dashboard.html", students=students)


# -----------------------
# Teacher Login
# -----------------------
@app.route("/teacher_login", methods=["POST"])
def teacher_login():
    email = request.form.get("email")
    password = request.form.get("password")

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute(
        "SELECT * FROM teachers WHERE email=%s AND password=%s",
        (email, password)
    )
    t = cur.fetchone()
    cur.close()
    db.close()

    if t:
        session["teacher"] = email
        return redirect("/teacher_dashboard")

    return "Invalid teacher credentials", 401


# -----------------------
# Weekly Email Reminder Thread
# -----------------------
def send_weekly_reminders_loop():
    time.sleep(5)

    while True:
        try:
            db = get_db()
            cur = db.cursor(dictionary=True)
            cur.execute(
                "SELECT email FROM students WHERE offer_filename IS NULL OR offer_filename=''"
            )
            rows = cur.fetchall()
            cur.close()
            db.close()

            for r in rows:
                send_email(r["email"], REMINDER_EMAIL_SUBJECT, REMINDER_EMAIL_BODY)

        except Exception as e:
            print("Reminder error:", e)

        time.sleep(7 * 24 * 3600)


Thread(target=send_weekly_reminders_loop, daemon=True).start()


# -----------------------
# RUN SERVER
# -----------------------
if __name__ == "__main__":
    app.run(debug=True)
