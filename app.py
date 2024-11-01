from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv
import os
import pymysql
from datetime import datetime, timedelta
from geopy.distance import geodesic  # New import for distance calculation
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit
import openai
from dotenv import load_dotenv

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

def get_chatbot_response(message):
    if "centroid" in message.lower() or "cluster" in message.lower():
        # Custom handling for BuzzRoute-specific questions
        response_text = "Centroid calculations are based on geographical clustering. Please specify a radius or other parameters."
        # You can add more specific responses here, or even integrate code to return real-time data if necessary.
    else:
        # Use OpenAI to process general questions
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=f"Assist in route optimization and clustering: {message}",
            max_tokens=150
        )
        response_text = response.choices[0].text.strip()
    
    return response_text


def calculate_centroid(coordinates):
    """Calculates the centroid of a group of coordinates."""
    if not coordinates:
        return None

    lat_sum = sum(coord[0] for coord in coordinates)
    long_sum = sum(coord[1] for coord in coordinates)

    centroid_lat = lat_sum / len(coordinates)
    centroid_long = long_sum / len(coordinates)

    return (centroid_lat, centroid_long)

def group_users_by_radius(user_coords, radius_km=5):
    """Groups users based on proximity and calculates centroids."""
    centroids = []
    grouped_users = []

    while user_coords:
        current_user = user_coords.pop(0)
        group = [current_user]

        for other_user in user_coords[:]:
            distance = geodesic(current_user, other_user).km
            if distance <= radius_km:
                group.append(other_user)
                user_coords.remove(other_user)

        centroid = calculate_centroid(group)
        centroids.append(centroid)
        grouped_users.append(group)

    return centroids, grouped_users

app = Flask(__name__)
socketio = SocketIO(app)
load_dotenv()

# OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Existing code...
# Code for database connection, time slots, and centroid detection...

# Chatbot route for rendering the chat page
@app.route("/chatbot")
def chatbot():
    return render_template("chatbot.html")

# Function to process chatbot responses based on user input
def get_chatbot_response(message):
    # Process the message here
    # For simplicity, you can use GPT to help analyze and respond
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=f"Assist in route optimization for transport. Given clusters and centroids, suggest optimal stops based on this input: {message}",
        max_tokens=150
    )
    return response.choices[0].text.strip()

# WebSocket event for receiving and sending messages
@socketio.on("message")
def handle_message(data):
    message = data["message"]
    response = get_chatbot_response(message)
    emit("response", {"message": response}, broadcast=True)




@app.route("/", methods=["GET", "POST"])
def index():
    time_slots = generate_time_slots()  # Generate time slots dynamically

    if request.method == "POST":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        age = request.form.get("age")
        time_slot = request.form.get("time_slot")
        source_lat = float(request.form.get("source_lat"))
        source_long = float(request.form.get("source_long"))
        dest_lat = float(request.form.get("dest_lat"))
        dest_long = float(request.form.get("dest_long"))

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

            return redirect(url_for('results'))
        except pymysql.MySQLError as err:
            return f"Failed to submit data: {err}"

    return render_template("index.html", api_key=gmaps_api_key, time_slots=time_slots)

@app.route("/results", methods=["GET"])
def results():
    # Fetch all user coordinates from the database
    cursor.execute("SELECT source_lat, source_long FROM sample_table")
    users = cursor.fetchall()

    # Convert users to a list of (latitude, longitude) tuples
    user_coords = [(float(lat), float(lng)) for lat, lng in users]

    # Group users and calculate centroids
    centroids, grouped_users = group_users_by_radius(user_coords, radius_km=5)

    return render_template("result.html", centroids=centroids, grouped_users=grouped_users)


if __name__ == "__main__":
    socketio.run(app, debug=True)


