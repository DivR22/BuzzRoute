from flask import Flask, render_template, redirect, url_for, session, flash, request
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, ValidationError
import bcrypt
import pymysql
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv
from geopy.distance import geodesic
from datetime import datetime, timedelta
import email_validator
import os

app = Flask(__name__)

# Load environment variables
load_dotenv()
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret_key")
gmaps_api_key = os.getenv("API_KEY")
host_sql = os.getenv("host")
user_sql = os.getenv("user")
database_sql = os.getenv("database")

# Database connection function
def get_db_connection():
    return pymysql.connect(
        host=host_sql,
        user=user_sql,
        database=database_sql
    )

# Flask-WTF Forms
class RegisterForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Register")

    def validate_email(self, field):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (field.data,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            raise ValidationError('Email Already Taken')

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

# Utility Functions
def generate_time_slots():
    """Generates time slots in 30-minute intervals from 00:00 to 23:30."""
    start_time = datetime.strptime('00:00', '%H:%M')
    end_time = datetime.strptime('23:30', '%H:%M')
    time_slots = []

    while start_time <= end_time:
        time_slots.append(start_time.strftime('%H:%M'))
        start_time += timedelta(minutes=30)
    
    return time_slots

def calculate_centroid(coordinates):
    """Calculates the centroid of a group of coordinates."""
    if not coordinates:
        return None

    lat_sum = sum(coord[0] for coord in coordinates)
    long_sum = sum(coord[1] for coord in coordinates)

    return (lat_sum / len(coordinates), long_sum / len(coordinates))

def insert_new_cluster(cursor, conn, centroid):
    """Inserts a new cluster with the given centroid coordinates into the database."""
    try:
        cursor.execute(
            "INSERT INTO clusters (centroid_lat, centroid_long) VALUES (%s, %s)",
            (centroid[0], centroid[1])
        )
        conn.commit()
    except pymysql.MySQLError as err:
        conn.rollback()
        print(f"Error inserting new cluster: {err}")

def update_existing_cluster(cursor, conn, cluster_id, new_centroid):
    """Updates an existing cluster's centroid with new coordinates."""
    try:
        cursor.execute(
            "UPDATE clusters SET centroid_lat = %s, centroid_long = %s WHERE cluster_id = %s",
            (new_centroid[0], new_centroid[1], cluster_id)
        )
        conn.commit()
    except pymysql.MySQLError as err:
        conn.rollback()
        print(f"Error updating cluster {cluster_id}: {err}")

def group_users_by_radius(user_coords, radius_km=5):
    """Groups users based on proximity and calculates centroids."""
    conn = get_db_connection()
    cursor = conn.cursor()
    centroids = []
    grouped_users = []

    while user_coords:
        current_user = user_coords.pop(0)
        group = [current_user]

        for other_user in user_coords[:]:
            if geodesic(current_user, other_user).km <= radius_km:
                group.append(other_user)
                user_coords.remove(other_user)

        centroid = calculate_centroid(group)
        centroids.append(centroid)
        grouped_users.append(group)

        # Check if centroid already exists in a cluster within range
        cursor.execute("SELECT cluster_id, centroid_lat, centroid_long FROM clusters")
        clusters = cursor.fetchall()
        for cluster_id, lat, lng in clusters:
            existing_centroid = (lat, lng)
            if geodesic(centroid, existing_centroid).km <= radius_km:
                update_existing_cluster(cursor, conn, cluster_id, centroid)
                break
        else:
            insert_new_cluster(cursor, conn, centroid)

    cursor.close()
    conn.close()
    return centroids, grouped_users

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        password = form.password.data
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                (name, email, hashed_password)
            )
            conn.commit()
            return redirect(url_for('login'))
        except pymysql.MySQLError as err:
            flash(f"Error: {err}")
        finally:
            cursor.close()
            conn.close()

    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user[3].encode('utf-8')):
            session['user_id'] = user[0]
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid email or password.")

    return render_template('login.html', form=form)

@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            return render_template('dashboard.html', user=user)
    return redirect(url_for('login'))

@app.route('/form', methods=['GET', 'POST'])
def form():
    time_slots = generate_time_slots()
    if request.method == "POST":
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO sample_table (first_name, last_name, email, age, source_lat, source_long, dest_lat, dest_long, time_slot)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    request.form.get("first_name"),
                    request.form.get("last_name"),
                    request.form.get("email"),
                    request.form.get("age"),
                    float(request.form.get("source_lat")),
                    float(request.form.get("source_long")),
                    float(request.form.get("dest_lat")),
                    float(request.form.get("dest_long")),
                    request.form.get("time_slot"),
                )
            )
            conn.commit()
            flash("Form submitted successfully!")
            return redirect(url_for('form'))
        except pymysql.MySQLError as err:
            flash(f"Failed to submit data: {err}")
        finally:
            cursor.close()
            conn.close()

    return render_template("form.html", api_key=gmaps_api_key, time_slots=time_slots)

@app.route('/about', methods=['GET'])
def about():
    return render_template("about.html")

@app.route('/results', methods=['GET'])
def results():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT source_lat, source_long FROM sample_table")
    users = cursor.fetchall()
    cursor.close()
    conn.close()

    user_coords = [(float(lat), float(lng)) for lat, lng in users]
    centroids, grouped_users = group_users_by_radius(user_coords)

    return render_template("result.html", centroids=centroids, grouped_users=grouped_users)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("Logged out successfully.")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)