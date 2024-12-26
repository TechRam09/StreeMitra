from flask import Flask, render_template, redirect, url_for, flash, session, send_from_directory
from flask_socketio import SocketIO, emit
from twilio.rest import Client
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from flask_mysqldb import MySQL
import os
from dotenv import load_dotenv
import bcrypt

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'fallback_secret_key')

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'streemitra'
mysql = MySQL(app)

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
EMERGENCY_CONTACT_NUMBER = os.getenv('EMERGENCY_CONTACT_NUMBER')
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# SocketIO Configuration
socketio = SocketIO(app, cors_allowed_origins="*")


# WTForms
class RegistrationForm(FlaskForm):
    name = StringField('name', validators=[DataRequired()])
    phno = StringField('phno', validators=[DataRequired()])
    e_phno = StringField('e_phno', validators=[DataRequired()])
    email = StringField('email', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])
    submit = SubmitField("register")


class LoginForm(FlaskForm):
    email = StringField('email', validators=[DataRequired()])
    password = PasswordField('password', validators=[DataRequired()])
    submit = SubmitField("login")


@app.route("/")
def landing_page():
    return render_template("landing.html")


@app.route("/user")
def user():
    return render_template("index.html")


@app.route("/admin")
def admin_page():
    return render_template("admin.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


def send_sms_alert(user_id, latitude, longitude):
    location_url = f"https://maps.google.com/?q={latitude},{longitude}"
    message_body = f"🚨 SOS Alert from {user_id}!\nLocation: {location_url}"
    try:
        message = twilio_client.messages.create(
            body=message_body,
            from_=TWILIO_PHONE_NUMBER,
            to=EMERGENCY_CONTACT_NUMBER
        )
        print(f"SMS sent successfully: SID {message.sid}")
    except Exception as e:
        print(f"Failed to send SMS: {e}")


@socketio.on("user_location")
def handle_user_location(data):
    print(f"Location received: {data}")
    emit("update_location", data, broadcast=True)


@socketio.on("sos_alert")
def handle_sos_alert(data):
    print(f"SOS Alert received: {data}")
    user_id = data.get("user_id")
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    send_sms_alert(user_id, latitude, longitude)
    


@app.route("/register", methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            name = form.name.data
            phno = form.phno.data
            e_phno = form.e_phno.data
            email = form.email.data
            password = form.password.data
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

            cursor = mysql.connection.cursor()
            cursor.execute(
                "INSERT INTO users (name, phno, e_phno, email, password) VALUES (%s, %s, %s, %s, %s)",
                (name, phno, e_phno, email, hashed_password)
            )
            mysql.connection.commit()
            cursor.close()

            flash("Registration successful! Please login.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Error: {e}", "danger")
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, password FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user[1].encode('utf-8')):
            session['user_id'] = user[0]
            flash("Login successful!", "success")
            return redirect(url_for('user'))
        else:
            flash("Login failed. Check your credentials.", "danger")

    return render_template('login.html', form=form)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
