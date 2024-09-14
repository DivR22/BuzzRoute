from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv
import os
import pymysql
from datetime import datetime, timedelta

app = Flask(__name__)

# Load environment variables
load_dotenv()
gmaps_api_key = os.getenv("API_KEY")
host_sql = os.getenv("host")
password_sql = os.getenv("password")
user_sql = os.getenv("user")
database_sql = os.getenv("database")

# Database connection
conn = pymysql.connect(host=host_sql, password=password_sql, user=user_sql, database=database_sql)
cursor = conn.cursor()

def generate_time_slots():
    """Generates time slots in 30-minute intervals from 00:00 to 23:30."""
    start_time = datetime.strptime('00:00', '%H:%M')
    end_time = datetime.strptime('23:30', '%H:%M')
    time_slots = []

    while start_time <= end_time:
        time_slots.append(start_time.strftime('%H:%M'))
        start_time += timedelta(minutes=30)
    
    return time_slots

@app.route("/", methods=["GET", "POST"])
def index():
    time_slots = generate_time_slots()  # Generate time slots dynamically

    if request.method == "POST":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        age = request.form.get("age")
        time_slot = request.form.get("time_slot")
        source_lat = request.form.get("source_lat")
        source_long = request.form.get("source_long")
        dest_lat = request.form.get("dest_lat")
        dest_long = request.form.get("dest_long")

        # Insert into the database
        try:
            cursor.execute(
                """
                INSERT INTO sample_table (first_name, last_name, email, age, source_lat, source_long, dest_lat, dest_long, time_slot)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (first_name, last_name, email, age, source_lat, source_long, dest_lat, dest_long, time_slot)
            )
            conn.commit()

            # Redirect to the result page and pass the data
            return redirect(url_for('result', first_name=first_name, last_name=last_name, email=email, age=age,
                                    time_slot=time_slot, source_lat=source_lat, source_long=source_long,
                                    dest_lat=dest_lat, dest_long=dest_long))
        except pymysql.MySQLError as err:
            return f"Failed to submit data: {err}"

    return render_template("index.html", api_key=gmaps_api_key, time_slots=time_slots)

@app.route("/result")
def result():
    # Get the data from the URL parameters
    first_name = request.args.get('first_name')
    last_name = request.args.get('last_name')
    email = request.args.get('email')
    age = request.args.get('age')
    time_slot = request.args.get('time_slot')
    source_lat = request.args.get('source_lat')
    source_long = request.args.get('source_long')
    dest_lat = request.args.get('dest_lat')
    dest_long = request.args.get('dest_long')

    # Render the result page
    return render_template("result.html", first_name=first_name, last_name=last_name, email=email, age=age,
                           time_slot=time_slot, source_lat=source_lat, source_long=source_long,
                           dest_lat=dest_lat, dest_long=dest_long)

if __name__ == "__main__":
    app.run(debug=True)
