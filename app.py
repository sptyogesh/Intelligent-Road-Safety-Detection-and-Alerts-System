# Required libraries
import threading
import time
from flask import Flask, current_app, jsonify, request, render_template, send_from_directory, url_for, redirect, flash, session, send_file, abort
from flask_mail import Mail, Message
from flask_socketio import SocketIO
from flask_cors import CORS
from datetime import datetime, date
from threading import Thread
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
import logging
import os
import requests
import psycopg2
from psycopg2.extras import DictCursor
import cv2
from pathlib import Path
from twilio.rest import Client
from ultralytics import YOLO
from dotenv import load_dotenv
import tempfile
import shutil
import io
import pytz

# Google API Libraries
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

app = Flask(__name__)
socketio = SocketIO(app)
CORS(app, resources={r"/*": {"origins": "http://127.0.0.1:2000"}})

app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = (os.getenv('MAIL_PORT'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

mail = Mail(app)
app.secret_key = "supersecretkey"

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'data/database-436009-e80a1bff3619.json'
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
drive_service = build('drive', 'v3', credentials=credentials)

IMAGE_FOLDER_ID = os.getenv('IMAGE_FOLDER_ID')
VIDEO_FOLDER_ID = os.getenv('VIDEO_FOLDER_ID')

def get_db_connection():
    """Establish a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT')
        )
        return conn
    except Exception as e:
        print(f"Database connection failed: {e}")
    abort(500)

@app.route('/')
def main():
    return render_template('home/home.html')

@app.route('/helpus')
def helpus():
    return render_template('home/helpus.html')

@app.route('/about')
def about():
    return render_template('home/about.html')

@app.route('/form')
def form():
    return render_template('home/form.html')

@app.route('/submit')
def submit():
    return render_template('home/submit.html')

# Error Handlers
@app.errorhandler(400)
def bad_request(e):
    return render_template('error/400.html'), 400

@app.errorhandler(401)
def unauthorized(e):
    return render_template('error/401.html'), 401

@app.errorhandler(403)
def forbidden(e):
    return render_template('error/403.html'), 403

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error/404.html'), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return render_template('error/405.html'), 405

@app.errorhandler(408)
def request_timeout(e):
    return render_template('error/408.html'), 408

@app.errorhandler(429)
def too_many_requests(e):
    return render_template('error/429.html'), 429

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error/500.html'), 500

@app.errorhandler(502)
def bad_gateway(e):
    return render_template('error/502.html'), 502

@app.errorhandler(503)
def service_unavailable(e):
    return render_template('error/503.html'), 503

@app.errorhandler(504)
def gateway_timeout(e):
    return render_template('error/504.html'), 504

@app.route('/Error-upload')
def error_500():
    return render_template('error/error_upload.html')

def not_found(error):
    return render_template('error/404.html'), 404


@app.route('/authorize/register')
def home():
    return redirect(url_for('register'))

@app.route('/driver_register', methods=['GET', 'POST'])
def driver_register():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        state = request.form.get('state')
        district = request.form.get('district')
        subdivision = request.form.get('subdivision')

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Check if email or phone already exists
            cursor.execute("SELECT id FROM driver_login WHERE email = %s OR phone = %s", (email, phone))
            existing_driver = cursor.fetchone()

            if existing_driver:
                flash("Email or phone number already registered.", "danger")
                return redirect(url_for('driver_register'))

            cursor.execute("INSERT INTO driver_login (name, phone, email, password, state, district, subdivision) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                           (name, phone, email, password, state, district, subdivision))
            driver_id = cursor.fetchone()[0]  # Get the newly created driver ID
            conn.commit()
            flash("Registration successful! Wait for confirmation.", "success")
            return redirect(url_for('login'))
        except psycopg2.Error as e:
            flash("Error: " + str(e), "danger")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()

    return render_template('auth/register.html')

# Driver login route
@app.route('/driver_login', methods=['GET', 'POST'])
def driver_login():
    # If the driver is already logged in, redirect to the driver dashboard
    if 'user_id' in session:
        if 'is_driver' in session and session['is_driver']:
            return redirect(url_for('driver_dashboard'))
        else:
            # If the user is logged in as a different role (admin or regular user), redirect accordingly
            return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "danger")
            return render_template('auth/login.html')

        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, password FROM driver_login WHERE email = %s", (email,))
            driver = cursor.fetchone()

            if driver:
                driver_id, stored_password = driver
                if check_password_hash(stored_password, password):
                    session['user_id'] = driver_id
                    session['is_driver'] = True  # Set session variable for driver
                    session.pop('is_admin', None)  # Ensure is_admin flag is cleared for drivers
                    flash("Login successful. Welcome, Driver!", "success")
                    return redirect(url_for('driver_dashboard'))  # Redirect to driver dashboard
                else:
                    flash("Invalid driver password.", "danger")
            else:
                flash("Driver not found.", "danger")

        except Exception as e:
            flash(f"An error occurred: {str(e)}", "danger")
        finally:
            cursor.close()
            conn.close()

    return render_template('auth/login.html')

@app.route('/driver-forgot-password', methods=['GET', 'POST'])
def driver_forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id FROM driver_login WHERE email = %s", (email,))
            user = cursor.fetchone()
            if user:
                s = URLSafeTimedSerializer(app.secret_key)
                token = s.dumps(email, salt='password-reset-salt')

                # Get the dynamic hostname
                host = request.host_url  # This gives you the scheme and host (e.g., http://example.com:2000/)
                reset_link = url_for('driver_reset_password', token=token, _external=True)

                # If you need to manually adjust the port
                reset_link = reset_link.replace('http://127.0.0.1:2000', host)

                msg = Message("Password Reset Request", recipients=[email],
                              body=f"Click the link to reset your password: {reset_link}")
                mail.send(msg)
                flash("A password reset link has been sent to your email.", "success")
            else:
                flash("Email not found.", "danger")
        except Exception as e:
            flash("An error occurred: " + str(e), "danger")
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('forgot_password'))
    return render_template('auth/forgot_password.html')

@app.route('/driver-reset-password/<token>', methods=['GET', 'POST'])
def driver_reset_password(token):
    s = URLSafeTimedSerializer(app.secret_key)
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except Exception:
        flash("The token is invalid or has expired.", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = generate_password_hash(request.form['new_password'])
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE driver_login SET password = %s WHERE email = %s", (new_password, email))
            conn.commit()
            flash("Your password has been updated!", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash("An error occurred: " + str(e), "danger")
        finally:
            cursor.close()
            conn.close()

    return render_template('auth/reset_password.html', token=token)

def driver_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or 'is_driver' not in session:
            return redirect(url_for('driver_login'))
        return f(*args, **kwargs)
    return decorated_function
@app.route('/driver_dashboard')

@driver_login_required  # Protect this route with the driver login required decorator
def driver_dashboard():
    conn = get_db_connection()
    if conn is None:
        flash("Database connection error. Please try again later.", "danger")
        return redirect(url_for('driver_login'))

    cursor = conn.cursor()
    try:
        # Get driver details from the database
        cursor.execute("SELECT name, phone, email, state, district, subdivision FROM driver_login WHERE id = %s", (session['user_id'],))
        driver = cursor.fetchone()

        if driver:
            driver_details = {
                "name": driver[0],
                "phone": driver[1],
                "email": driver[2],
                "state": driver[3],
                "district": driver[4],
                "subdivision": driver[5]
            }
        else:
            flash("Driver details not found.", "danger")
            return redirect(url_for('driver_login'))

    except Exception as e:
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for('driver_login'))
    finally:
        cursor.close()
        conn.close()

    return render_template('driver/driver_home.html', driver_details=driver_details)



@app.route('/map')
def view_map():
    """
    Render the map page.
    """
    return render_template('driver/map.html')


@app.route('/case-locations')
def case_locations():
    """
    Fetch case data with GPS locations.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Query to fetch necessary data
        cursor.execute("""
            SELECT id, name, latitude, longitude, description, upload_date, upload_time  
            FROM user_details
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """)
        case_data = cursor.fetchall()

        # Convert to JSON format
        cases = [
            {
                "id": case[0],
                "name": case[1],
                "latitude": float(case[2]),
                "longitude": float(case[3]),
                "description": case[4],
                "upload_date": case[5].strftime('%a, %d %b %Y') if case[5] else None,
                "upload_time": case[6].strftime('%I:%M:%S:%p') if case[6] else None
            }
            for case in case_data
        ]
        return jsonify(cases)

    except Exception as e:
        print(f"Error fetching case locations: {e}")
        return jsonify({"error": "Could not fetch case locations."}), 500

    finally:
        cursor.close()
        conn.close()


@app.route('/driver_notify')
@driver_login_required  # Protect this route with the driver login required decorator
def driver_notify():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, state FROM driver_place_details;')
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('driver/driver_data.html', users=users)

@app.route('/place/<int:user_id>')
@driver_login_required
def driver_details(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM driver_place_details WHERE id = %s;', (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user is None:
        return redirect(url_for('driver_notify'))
    
    return render_template('driver/driver_details.html', user=user)

@app.route('/delete/<int:user_id>', methods=['POST'])
@driver_login_required
def delete_driver(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch the data to be deleted
    cursor.execute('SELECT * FROM driver_place_details WHERE id = %s;', (user_id,))
    user = cursor.fetchone()

    if user:
        # Insert data into driver_delete_detail with current date and time for deletion
        cursor.execute(''' 
            INSERT INTO driver_delete_detail 
            (id, state, district, subdivision, pincode, latitude, longitude, street, 
             submission_date, submission_time, deletion_date, deletion_time) 
            OVERRIDING SYSTEM VALUE
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE, CURRENT_TIME AT TIME ZONE 'Asia/Kolkata')
        ''', user)

        # Delete from original table
        cursor.execute('DELETE FROM driver_place_details WHERE id = %s;', (user_id,))
        conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for('driver_notify'))

@app.route('/driver_history', methods=['GET'])
@driver_login_required  # If you want to restrict access to logged-in users
def driver_history():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch all records from the driver_delete_detail table
    cursor.execute('SELECT * FROM driver_delete_detail;')
    deleted_data = cursor.fetchall()

    cursor.close()
    conn.close()

    # Render the data in a template or return as JSON
    return render_template('driver/driver_history.html', deleted_data=deleted_data)
    # Alternatively, to return JSON:
    # return jsonify(deleted_data)

@app.route('/restore/<int:user_id>', methods=['POST'])
@driver_login_required
def restore_driver(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Select the data from driver_delete_detail for the specific user_id, including the id
    cursor.execute("SELECT id, state, district, subdivision, pincode, latitude, longitude, street, submission_date, submission_time FROM driver_delete_detail WHERE id = %s", (user_id,))
    deleted_record = cursor.fetchone()

    if deleted_record:
        # Insert the data into driver_place_details, using OVERRIDING SYSTEM VALUE to set the same id
        cursor.execute(''' 
            INSERT INTO driver_place_details (id, state, district, subdivision, pincode, latitude, longitude, street, submission_date, submission_time) 
            OVERRIDING SYSTEM VALUE 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', deleted_record)

        # Remove the restored record from driver_delete_detail
        cursor.execute('DELETE FROM driver_delete_detail WHERE id = %s;', (user_id,))
        conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for('driver_history'))

@app.route('/map')
@driver_login_required
def map_view():
    lat = request.args.get('lat', default=28.6139)  # Default to a location if not provided
    lng = request.args.get('lng', default=77.2090)  # Default to a location if not provided
    return render_template('driver/driver_map.html', lat=lat, lng=lng)

@app.route('/driver_logout')
def driver_logout():
    session.pop('user_id', None)  # Remove user ID from session
    session.pop('is_driver', None)  # Remove driver indicator from session
    flash("You have been logged out.", "success")
    return redirect(url_for('driver_login'))  # Redirect to driver login page

##### driver end #####

##### user stare ####

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:  # Check if user is logged in
            return redirect(url_for('login'))  # Redirect to login if not logged in
        return f(*args, **kwargs)
    return decorated_function

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        state = request.form.get('state')
        district = request.form.get('district')
        subdivision = request.form.get('subdivision')

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Check if email or phone already exists
            cursor.execute("SELECT id FROM user_login_verify WHERE email = %s OR phone = %s", (email, phone))
            existing_user = cursor.fetchone()

            if existing_user:
                flash("Email or phone number already registered.", "danger")
                return redirect(url_for('register'))
            
            # Check if email or phone already exists
            cursor.execute("SELECT id FROM user_login_success WHERE email = %s OR phone = %s", (email, phone))
            existing_user = cursor.fetchone()

            if existing_user:
                flash("Email or phone number already registered.Please Wait for Confirmation", "danger")
                return redirect(url_for('register'))

            cursor.execute("INSERT INTO user_login_verify (name, phone, email, password, state, district, subdivision) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                           (name, phone, email, password, state, district, subdivision))
            conn.commit()
            flash("Registration successful! Wait for confirmation.", "success")
            return redirect(url_for('login'))
        except psycopg2.Error as e:
            flash("Error: " + str(e), "danger")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()

    return render_template('auth/register.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    
    if 'user_id' in session:
        if 'is_admin' in session and session['is_admin']:
            return redirect(url_for('dashboard'))  # Admin dashboard
        elif 'is_driver' in session and session['is_driver']:
            return redirect(url_for('driver_dashboard'))  # Driver dashboard
        else:
            return redirect(url_for('dashboard'))  # Regular user dashboard
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM user_login_success WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        email_exists = user is not None
        password_correct = email_exists and check_password_hash(user[1], password)

        # Flash messages based on login attempt
        if email_exists and password_correct:
            session['user_id'] = user[0]  # Store user ID in session
            session.pop('is_admin', None) 
            flash("Login successfully.", "success") 
            return redirect(url_for('dashboard'))  # Redirect to the user dashboard
        elif not email_exists and not password_correct:
            flash("Invalid email and password.", "danger")  # Both incorrect
        elif not email_exists:
            flash("Invalid email.", "danger")  # Email incorrect
        elif email_exists and not password_correct:
            flash("Invalid password.", "danger")  # Password incorrect

    return render_template('auth/login.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if 'user_id' in session:
        if 'is_admin' in session and session['is_admin']:
            return redirect(url_for('dashboard'))  # Admin dashboard
        elif 'is_driver' in session and session['is_driver']:
            return redirect(url_for('driver_dashboard'))  # Driver dashboard
        else:
            return redirect(url_for('dashboard'))  # Regular user dashboard
        
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "danger")
            return render_template('auth/login.html')

        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, password FROM admin_login WHERE email = %s", (email,))
            admin = cursor.fetchone()

            if admin:
                admin_id, stored_password = admin
                # Check if the entered password matches the stored password
                if stored_password == password:
                    session['user_id'] = admin_id
                    session['is_admin'] = True 
                    flash("Login successfully.", "success") 
                    return redirect(url_for('dashboard'))  # Redirect to admin dashboard
                else:
                    flash("Invalid admin password.", "danger")
            else:
                flash("Admin not found.", "danger")

        except Exception as e:
            flash(f"An error occurred: {str(e)}", "danger")
        finally:
            cursor.close()
            conn.close()

    return render_template('auth/login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id FROM user_login_success WHERE email = %s", (email,))
            user = cursor.fetchone()
            if user:
                s = URLSafeTimedSerializer(app.secret_key)
                token = s.dumps(email, salt='password-reset-salt')

                # Get the dynamic hostname
                host = request.host_url  # This gives you the scheme and host (e.g., http://example.com:2000/)
                reset_link = url_for('reset_password', token=token, _external=True)

                # If you need to manually adjust the port
                reset_link = reset_link.replace('http://127.0.0.1:2000', host)

                msg = Message("Password Reset Request", recipients=[email],
                              body=f"Click the link to reset your password: {reset_link}")
                mail.send(msg)
                flash("A password reset link has been sent to your email.", "success")
            else:
                flash("Email not found.", "danger")
        except Exception as e:
            flash("An error occurred: " + str(e), "danger")
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('forgot_password'))
    return render_template('auth/forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    s = URLSafeTimedSerializer(app.secret_key)
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except Exception:
        flash("The token is invalid or has expired.", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = generate_password_hash(request.form['new_password'])
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE user_login_success SET password = %s WHERE email = %s", (new_password, email))
            conn.commit()
            flash("Your password has been updated!", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash("An error occurred: " + str(e), "danger")
        finally:
            cursor.close()
            conn.close()

    return render_template('auth/reset_password.html', token=token)

@app.route('/admin/approve_users', methods=['GET', 'POST'])
@login_required
def approve_users():
    if 'is_admin' not in session or not session['is_admin']:
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if conn is None:
        return "Database connection error", 500

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        action = request.form.get('action')

        try:
            with conn.cursor() as cur:
                if action == 'approve':
                    # Move user to user_login_success table
                    cur.execute("INSERT INTO user_login_success (name, phone, email, password, state, district, subdivision) "
                                "SELECT name, phone, email, password, state, district, subdivision FROM user_login_verify WHERE id = %s", (user_id,))
                    
                    cur.execute("DELETE FROM user_login_verify WHERE id = %s", (user_id,))
                    flash("User approved successfully!", "success")
                    
                    # Send approval email
                    send_email(user_id, "Registration Approved", "Your registration has been approved!")
                elif action == 'reject':
                    cur.execute("DELETE FROM user_login_verify WHERE id = %s", (user_id,))
                    flash("User rejected successfully!", "danger")
                    
                    # Send rejection email
                    send_email(user_id, "Registration Rejected", "Your registration has been rejected.")
                    
                conn.commit()
        except Exception as e:
            conn.rollback()
            flash("An error occurred: " + str(e), "danger")
        finally:
            conn.close()
        return redirect(url_for('approve_users'))

    # Fetch all pending users
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, phone, email, password, state, district, subdivision FROM user_login_verify;")
        pending_users = cur.fetchall()

    return render_template('user/approve.html', pending_users=pending_users)

@app.route('/map_info')
@login_required
def map_info():
    lat = request.args.get('lat', default=28.6139)  # Default to a location if not provided
    lng = request.args.get('lng', default=77.2090)  # Default to a location if not provided
    return render_template('user/user_map.html', lat=lat, lng=lng)

def send_email(user_id, subject, body):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM user_login_verify WHERE id = %s", (user_id,))
    user_email = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    msg = Message(subject=subject, recipients=[user_email])
    msg.body = body
    mail.send(msg)
    
@app.route('/logout')
def logout():
    session.pop('user_id', None)  # Remove user ID from session
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Render the main page with user or admin details."""
    conn = get_db_connection()
    if conn is None:
       return abort(500)

    user_id = session['user_id']
    is_admin = session.get('is_admin', False)

    with conn.cursor() as cur:
        if is_admin:
            # Admin can view all user details
            cur.execute("SELECT name, phone, email, employee, aadhar, gender, state, district, dob FROM admin_login WHERE id = %s", (user_id,))
            current_user = cur.fetchone()

            # Fetch all user details for admins
            cur.execute("""
                SELECT u.id, u.name, u.phone, u.state, u.district, u.subdivision, u.pincode, 
                       u.latitude, u.longitude, u.upload_date, u.upload_time, u.file_name
                FROM user_details u
                ORDER BY u.id;
            """)
            users = cur.fetchall()

        else:
            # Regular user can only view users from the same district
            cur.execute("SELECT name, phone, email, state, district, subdivision FROM user_login_success WHERE id = %s", (user_id,))
            current_user = cur.fetchone()

            if current_user:
                district = current_user[4]  # Get the user's district

                # Fetch details for users in the same district
                cur.execute("""
                    SELECT u.id, u.name, u.phone, u.state, u.district, u.subdivision, u.pincode, 
                           u.latitude, u.longitude, u.upload_date, u.upload_time, u.file_name
                    FROM user_details u
                    WHERE u.district = %s
                    ORDER BY u.id;
                """, (district,))
                users = cur.fetchall()
            else:
                users = []  # If no user found

    # Process user data for the frontend
    data_list = [
        {
            'id': user[0],
            'name': user[1],
            'phone': user[2],
            'state': user[3],
            'district': user[4],
            'subdivision': user[5],
            'pincode': user[6],
            'latitude': user[7],
            'longitude': user[8],
            'upload_date': user[9],
            'upload_time': user[10],
            'file_name': user[11],
            'file_path': get_file_path(user[11])
        }
        for user in users
    ]

    return render_template('user/inbox.html', users=data_list, current_user=current_user, is_admin=is_admin)

@app.route('/add_admin', methods=['GET', 'POST'])
@login_required
def add_admin():
    """Allows an admin to create a new admin account."""
    if not session.get('is_admin', False):
        return abort(403)

    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        email = request.form['email']
        employee=request.form['employee']
        aadhar=request.form['aadhar']
        gender=request.form['gender']
        state=request.form['state']
        district=request.form['district']
        dob=request.form['dob']
        password = request.form['password']

        conn = get_db_connection()
        if conn is None:
            return abort(500)

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO admin_login (name, phone, email, password, employee, aadhar, gender, state, district, dob)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (name, phone, email, password, employee, aadhar, gender, state, district, dob))
                conn.commit()

            flash("New admin created successfully", "success")
            return redirect(url_for('dashboard'))

        except psycopg2.IntegrityError:
            conn.rollback()
            flash("Error: Phone or email already exists", "error")
        except Exception as e:
            conn.rollback()
            flash(f"An error occurred: {str(e)}", "error")
        finally:
            conn.close()

    return render_template('user/add_admin.html')


"""experimntal data here"""######################
###################################################
#################################################
################################################


@app.route('/manage_admins')
@login_required
def manage_admins():
    if not session.get('is_admin', False):
        return abort(403)
    
    conn = get_db_connection()
    cur = conn.cursor()

    # Fetch admins from the database ordered alphabetically by name
    cur.execute("SELECT id, name, email, phone, employee, aadhar, gender, state, district, dob FROM admin_login ORDER BY name ASC")
    admins = cur.fetchall()

    # Convert the result into a list of dictionaries for easier rendering in the template
    admins_list = [{"id": admin[0], "name": admin[1], "email": admin[2], "phone": admin[3],"employee": admin[4], "aadhar": admin[5], "gender": admin[6],  "state": admin[7],  "district": admin[8], "dob": admin[9]} for admin in admins]

    cur.close()
    conn.close()

    # Render the page with the sorted admins
    return render_template('user/manage_admins.html', admins=admins_list)

@app.route('/remove_admin', methods=['POST'])
@login_required
def remove_admin():
    
    if not session.get('is_admin', False):
        return abort(403)
    
    admin_id = request.form['admin_id']
    conn = get_db_connection()
    if conn is None:
        flash("Database connection error", 'danger')
        return redirect(url_for('manage_admins'))

    cursor = conn.cursor()
    cursor.execute('DELETE FROM admin_login WHERE id = %s', (admin_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Admin removed successfully!', 'success')
    return redirect(url_for('manage_admins'))

@app.route('/edit_admin/<int:admin_id>', methods=['GET', 'POST'])
@login_required
def edit_admin(admin_id):
    
    if not session.get('is_admin', False):
        return abort(403)
    
    conn = get_db_connection()
    cur = conn.cursor()

    # Fetch admin data from the database
    cur.execute("SELECT id, name, email, phone, employee, aadhar, gender, state, district, dob FROM admin_login WHERE id = %s", (admin_id,))
    admin = cur.fetchone()

    # If no admin is found
    if not admin:
        return "Admin not found", 404

    # Convert tuple to dictionary
    admin_dict = {
        "id": admin[0], "name": admin[1], "email": admin[2], "phone": admin[3],
        "employee": admin[4], "aadhar": admin[5], "gender": admin[6],
        "state": admin[7], "district": admin[8], "dob": admin[9]
    }

    # Handle the POST request to update the admin data
    if request.method == 'POST':
        
        # Get the updated values from the form
        updated_name = request.form.get('name')
        updated_email = request.form.get('email')
        updated_phone = request.form.get('phone')
        updated_password = request.form.get('password')
        updated_employee = request.form.get('employee')
        updated_aadhar = request.form.get('aadhar')
        updated_gender = request.form.get('gender')
        updated_state = request.form.get('state')
        updated_district = request.form.get('district')
        updated_dob = request.form.get('dob')
        
        # Validate the required fields
        if not updated_name or not updated_email or not updated_phone or not updated_employee or not updated_aadhar:
            flash("Please fill in all required fields.", "danger")
            return render_template('user/edit_admin.html', admin=admin_dict)

        # If password is updated, we must update it in the database
        if updated_password:
            # Only update password if it's provided
            password_to_update = updated_password
        else:
            # If no new password is provided, keep the old password
            password_to_update = admin_dict['password']
        
        try:
            cur.execute("""
                UPDATE admin_login
                SET name = %s, email = %s, phone = %s, employee = %s, aadhar = %s, gender = %s, state = %s, district = %s, dob = %s, password = %s
                WHERE id = %s
            """, (updated_name, updated_email, updated_phone, updated_employee, updated_aadhar, updated_gender, updated_state, updated_district, updated_dob, password_to_update, admin_id))
            conn.commit()

            flash("Admin details updated successfully!", "success")
        except Exception as e:
            app.logger.error(f"Error updating admin: {e}")
            conn.rollback()
            flash("There was an error updating the admin information", "danger")
            return render_template('user/edit_admin.html', admin=admin_dict)
        finally:
            cur.close()
            conn.close()

        # Redirect after success (could be to the admin management page, for example)
        return redirect(url_for('manage_admins'))

    # Render the template with admin data (GET request)
    return render_template('user/edit_admin.html', admin=admin_dict)

###########################
############################
#############################
############################
#############################
@app.route('/user/<int:user_id>')
@login_required
def user_details(user_id):
    """Render detailed information for a specific user."""
    conn = get_db_connection()
    if conn is None:
        return abort(500)

    current_user_id = session['user_id']
    is_admin = session.get('is_admin', False)

    with conn.cursor() as cur:
        if is_admin:
            # Admin can view any user's details
            cur.execute("""SELECT u.id, u.name, u.phone, u.state, u.district, u.subdivision, u.pincode,
                                   u.latitude, u.longitude, u.street, u.description, u.upload_date, u.upload_time, u.file_name
                           FROM user_details u
                           WHERE u.id = %s""", (user_id,))
        else:
            # Regular user can only view their district details 
            cur.execute("""SELECT u.id, u.name, u.phone, u.state, u.district, u.subdivision, u.pincode,
                                   u.latitude, u.longitude, u.street, u.description, u.upload_date, u.upload_time, u.file_name
                           FROM user_details u
                           INNER JOIN user_login_success ul ON ul.district = u.district
                           WHERE u.id = %s AND ul.id = %s;""", (user_id, current_user_id))

        user = cur.fetchone()

    if not user:
        return abort(404)

    user_data = {
        'id': user[0],
        'name': user[1],
        'phone': user[2],
        'state': user[3],
        'district': user[4],
        'subdivision': user[5],
        'pincode': user[6],
        'latitude': user[7],
        'longitude': user[8],
        'street': user[9],
        'description': user[10],
        'upload_date': user[11],
        'upload_time': user[12],
        'file_name': user[13],
        'file_path': get_file_path(user[13])
    }
    
    return render_template('user/user.html', user=user_data)

@app.route('/chart')
@login_required
def chart():
    """Render a chart based on user data."""
    conn = get_db_connection()
    if conn is None:
        return abort(500)

    user_id = session['user_id']
    is_admin = session.get('is_admin', False)

    with conn.cursor() as cur:
        if is_admin:
            cur.execute("""SELECT u.state, COUNT(u.id)
                           FROM user_details u
                           GROUP BY u.state;""")
        else:
            # Get the user's district
            cur.execute("SELECT district FROM user_login_success WHERE id = %s", (user_id,))
            district = cur.fetchone()[0]

            cur.execute("""SELECT u.state, COUNT(u.id)
                           FROM user_details u
                           WHERE u.district = %s
                           GROUP BY u.state;""", (district,))

        state_count = cur.fetchall()

    chart_data = {
        "labels": [row[0] for row in state_count],
        "data": [row[1] for row in state_count],
    }

    return render_template('user/chart.html', chart_data=chart_data)

@app.route('/user/<int:user_id>/close', methods=['POST'])
@login_required
def close_case(user_id):
    conn = get_db_connection()
    if conn is None:
        return abort(500)

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM user_details WHERE id = %s", (user_id,))
            user = cur.fetchone()

            if user is None:
                return abort(404)

            cur.execute("""INSERT INTO closed_cases (id, name, phone, state, district, subdivision, 
                                                      pincode, latitude, longitude, street, description, 
                                                      upload_date, upload_time, file_name, 
                                                      case_closed_date, case_closed_time)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (user[0], user[1], user[2], user[3], user[4], user[5],
                              user[6], user[7], user[8], user[9], user[10],
                              user[11], user[12], user[13], date.today(), datetime.now().time()))

            cur.execute("DELETE FROM user_details WHERE id = %s", (user_id,))
            conn.commit()
            return redirect(url_for('dashboard'))

    except Exception as e:
        conn.rollback()
        return abort(500)

    finally:
        conn.close()

@app.route('/reopen')
@login_required
def reopen_cases():
    """Render a list of closed cases for reopening."""
    conn = get_db_connection()
    if conn is None:
        return abort(500)

    user_id = session['user_id']
    is_admin = session.get('is_admin', False)

    with conn.cursor() as cur:
        if is_admin:
            # Admin can view all closed cases
            cur.execute("SELECT id, name, subdivision, upload_date, upload_time, case_closed_date, case_closed_time FROM closed_cases;")
        else:
            # Regular user can only view closed cases in their district
            cur.execute("SELECT name, district FROM user_login_success WHERE id = %s", (user_id,))
            user = cur.fetchone()
            district = user[1] if user else None
            
            if district:
                cur.execute("SELECT id, name, subdivision, upload_date, upload_time, case_closed_date, case_closed_time FROM closed_cases WHERE district = %s;", (district,))
            else:
                return "No closed cases found for your district.", 404

        cases = cur.fetchall()

        case_list = []
        for case in cases:
            case_data = {
                'id': case[0],
                'name': case[1],
                'subdivision': case[2],
                'upload_date': case[3],
                'upload_time': case[4],
                'case_closed_date': case[5],
                'case_closed_time': case[6],
            }
            case_list.append(case_data)

    return render_template('user/reopen.html', cases=case_list)

@app.route('/reopen/<int:case_id>', methods=['POST'])
@login_required
def restore_case(case_id):
    conn = get_db_connection()
    if conn is None:
        return abort(500)

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM closed_cases WHERE id = %s", (case_id,))
            case = cur.fetchone()

            if case is None:
                return "Closed case not found", 404

            cur.execute("""INSERT INTO user_details (id, name, phone, state, district, subdivision, 
                                                      pincode, latitude, longitude, street, description, 
                                                      upload_date, upload_time, file_name)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (case[0], case[1], case[2], case[3], case[4], case[5],
                              case[6], case[7], case[8], case[9], case[10],
                              case[11], case[12], case[13]))

            cur.execute("DELETE FROM closed_cases WHERE id = %s", (case_id,))
            conn.commit()
            return redirect(url_for('reopen_cases'))

    except Exception as e:
        conn.rollback()
        print(e)
        return abort(500)

    finally:
        conn.close()

@socketio.on('connect')
def handle_connect():
    print("Client connected")

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")

def notify_users():
    """Notify users about file updates."""
    with current_app.app_context():
        conn = get_db_connection()
        if conn is None:
            return
        
        with conn.cursor() as cur:
            cur.execute("""SELECT u.id, u.name, u.upload_date, u.upload_time, u.file_name
                            FROM user_details u
                            ORDER BY u.id;""")
            users_files = cur.fetchall()

        grouped_data = {}
        for user in users_files:
            user_id = user[0]
            file_names_str = user[3]

            if not file_names_str:
                print(f"No files found for user ID {user_id}.")
                continue

            file_names = file_names_str.split(',') if isinstance(file_names_str, str) else []
            for file_name in file_names:
                file_name = file_name.strip()
                if file_name:
                    file_path = get_file_path(file_name)
                    if file_path:
                        if user_id not in grouped_data:
                            grouped_data[user_id] = {
                                'id': user_id,
                                'name': user[1],
                                'upload_date': str(user[2]),
                                'upload_time': str(user[3]),
                                'file_paths': []
                            }
                        grouped_data[user_id]['file_paths'].append(file_path)

        socketio.emit('update', list(grouped_data.values()))

def background_task():
    """Background task to periodically notify users."""
    with app.app_context():
        while True:
            time.sleep(0.8)
            notify_users()


##### google cloud image video fetch #####

def download_file_from_drive(file_id):
    request = drive_service.files().get_media(fileId=file_id)
    file_data = io.BytesIO()
    downloader = MediaIoBaseDownload(file_data, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()

    file_data.seek(0)
    return file_data

@app.route('/uploads/image/<filename>')
def uploaded_image(filename):
    try:
        response = drive_service.files().list(
            q=f"'{IMAGE_FOLDER_ID}' in parents and name='{filename}'",
            fields="files(id, name)"
        ).execute()
        files = response.get('files', [])

        if not files:
            return abort(404)

        file_id = files[0]['id']
        file_data = download_file_from_drive(file_id)
        return send_file(file_data, mimetype='image/jpeg')
    except Exception as e:
        return str(e), 500

@app.route('/uploads/video/<filename>')
def uploaded_video(filename):
    mime_types = {
        '.mp4': 'video/mp4',
        '.mkv': 'video/x-matroska',
        '.webm': 'video/webm',
        '.ogg': 'video/ogg'
    }
    file_extension = os.path.splitext(filename)[1].lower()
    mime_type = mime_types.get(file_extension, 'application/octet-stream')

    try:
        response = drive_service.files().list(
            q=f"'{VIDEO_FOLDER_ID}' in parents and name='{filename}'",
            fields="files(id, name)"
        ).execute()
        files = response.get('files', [])

        if not files:
            return abort(404)

        file_id = files[0]['id']
        file_data = download_file_from_drive(file_id)
        return send_file(file_data, mimetype=mime_type)
    except Exception as e:
        return str(e), 500

def get_file_path(file_name):
    if not file_name:
        return []

    file_names = [name.strip() for name in file_name.split(',')]
    paths = []
    
    for name in file_names:
        file_extension = os.path.splitext(name)[1].lower()
        if file_extension in ['.jpg', '.jpeg', '.png', '.gif']:
            paths.append(url_for('uploaded_image', filename=name.lstrip('/')))
        elif file_extension in ['.mp4', '.mkv', '.webm', '.ogg']:
            paths.append(url_for('uploaded_video', filename=name.lstrip('/')))
    
    return paths


##############################################


""" here now upload file and detection manage that upload to drive and data will be upload to database"""

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler()]
)

# Load YOLO model
model = YOLO('data/best.pt')

# Allowed file extensions
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'mp4', 'mkv', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_next_sequence(date_str):
    conn = psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT')
    )
    with conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT last_sequence FROM daily_file_sequence WHERE date = %s", (date_str,))
            result = cursor.fetchone()

            if result:
                next_sequence = result['last_sequence'] + 1
                cursor.execute("UPDATE daily_file_sequence SET last_sequence = %s WHERE date = %s", (next_sequence, date_str))
            else:
                # Handle case where no sequence is found (insert initial record)
                next_sequence = 1
                cursor.execute("INSERT INTO daily_file_sequence (date, last_sequence) VALUES (%s, %s)", (date_str, next_sequence))
                
            conn.commit()
            return next_sequence

def generate_unique_filename(base_date, extension, sequence):
    return f"{base_date}_{sequence:05d}.{extension}"

def upload_to_drive(file_path, filename, folder_id):
    file_metadata = {'name': filename, 'parents': [folder_id]}
    media = MediaFileUpload(file_path, resumable=True)
    try:
        drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        logging.info(f"File '{filename}' uploaded to Google Drive successfully.")
        return True
    except Exception as e:
        logging.error(f"Failed to upload '{filename}' to Google Drive: {e}")
        return False

def yolo_annotate(file_path):
    try:
        if file_path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'}:
            results = model(str(file_path))
            return [{"label": model.names[int(box.cls)], "accuracy": round(float(box.conf) * 100, 2)} for box in results[0].boxes]
        elif file_path.suffix.lower() in {'.mp4', '.mkv'}:
            video = cv2.VideoCapture(str(file_path))
            detections = []
            while True:
                ret, frame = video.read()
                if not ret:
                    break
                results = model(frame)
                detections.extend([{"label": model.names[int(box.cls)], "accuracy": round(float(box.conf) * 100, 2)} for box in results[0].boxes])
            video.release()
            return detections
    except Exception as e:
        logging.error(f"Error during YOLO annotation for {file_path}: {e}")
    return []


@app.route('/upload', methods=['POST'])
def upload():
    utc_now = datetime.now(pytz.utc)
    ist_timezone = pytz.timezone('Asia/Kolkata')
    ist_now = utc_now.astimezone(ist_timezone)
    # Format the date and time in IST
    upload_date = ist_now.date()
    upload_time = ist_now.time()
    try:
        # Get form data and files
        data = request.form
        files = request.files.getlist('file')

        if not files:
            logging.warning("No files uploaded.")
            return jsonify({"status": "error", "message": "No files uploaded."}), 400

        # Save the files first in the main thread
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)

        saved_file_paths = []
        for file in files:
            if allowed_file(file.filename):
                file_ext = file.filename.rsplit('.', 1)[1].lower()
                temp_file_path = temp_dir / file.filename
                file.save(temp_file_path)
                saved_file_paths.append(temp_file_path)

        # Start the background task (this will run asynchronously)
        def background_task():
            annotation_dir = Path("annotation")
            annotation_dir.mkdir(exist_ok=True)

            generated_filenames = []
            overall_detections = []
            now = datetime.now()
            date_str = now.strftime("%Y%m%d")

            # Process each file uploaded
            for file_path in saved_file_paths:
                detections = yolo_annotate(file_path)

                # If no detections found, skip the file
                if not detections:
                    logging.info(f"Skipping file {file_path.name} as no annotations were detected.")
                    continue

                overall_detections.append(detections)

                # Generate a unique filename for the annotated file
                next_sequence = get_next_sequence(date_str)
                unique_filename = generate_unique_filename(date_str, file_path.suffix[1:], next_sequence)
                annotated_file_path = annotation_dir / unique_filename
                shutil.move(str(file_path), annotated_file_path)

                # Add the file to the list for uploading and database insertion
                generated_filenames.append(annotated_file_path)

            # Upload annotated files to Google Drive
            for annotated_file_path in generated_filenames:
                unique_filename = annotated_file_path.name
                folder_id = IMAGE_FOLDER_ID if annotated_file_path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'} else VIDEO_FOLDER_ID
                if upload_to_drive(annotated_file_path, unique_filename, folder_id):
                    # After successful upload, delete the original file
                    logging.info(f"Deleting original file: {annotated_file_path}")
                    os.remove(annotated_file_path)

            # Only insert details of files with annotations into the database
            if generated_filenames:
                conn = psycopg2.connect(
                    dbname=os.getenv('DB_NAME'),
                    user=os.getenv('DB_USER'),
                    password=os.getenv('DB_PASSWORD'),
                    host=os.getenv('DB_HOST'),
                    port=os.getenv('DB_PORT')
                )
                cursor = conn.cursor()

                # Extract data from form
                name = data.get('name')
                phone = data.get('phone')
                state = data.get('state')
                district = data.get('district')
                subdivision = data.get('subdivision')
                pincode = data.get('pincode')
                street = data.get('street')
                description = data.get('description')
                latitude = data.get('latitude')
                longitude = data.get('longitude')
                file_names = ','.join([file.name for file in generated_filenames])  # Join the list of filenames

                cursor.execute(""" 
                    INSERT INTO user_details (name, phone, state, district, subdivision, pincode, latitude, longitude, street, description, upload_date, upload_time, file_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, subdivision;
                """, (name, phone, state, district, subdivision, pincode, latitude, longitude, street, description, upload_date, upload_time, file_names))

                user_id, user_subdivision = cursor.fetchone()
                logging.info(f"Inserted user_details with ID {user_id}")
                logging.info("Successfully processed user submission.")

                cursor.execute(""" 
                    INSERT INTO driver_place_details (state, district, subdivision, pincode, latitude, longitude, street)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                """, (state, district, subdivision, pincode, latitude, longitude, street))

                logging.info("Successfully processed driver submission.")
                conn.commit()
                
                send_sms = False
                if user_id and user_subdivision:  # Ensure user data is inserted
                    if state and district and subdivision:  # Ensure driver data is inserted
                        # Fetch phone numbers based on district match
                        email_list = get_emails(subdivision=user_subdivision)

                        if email_list:
                            # Define subject and body content based on subdivision
                            subject = f"Important Notification for {subdivision}"
                            body = f"""
                            <html>
                                <head>
                                    <style>
                                        body {{
                                            font-family: Arial, sans-serif;
                                            color: #333;
                                            background-color: #f4f4f9;
                                            padding: 20px;
                                        }}
                                        .email-container {{
                                            background-color: #ffffff;
                                            border: 1px solid #dddddd;
                                            padding: 20px;
                                            border-radius: 8px;
                                            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                                        }}
                                        h2 {{
                                            color: #0056b3;
                                        }}
                                        .email-header {{
                                            background-color: #0056b3;
                                            color: white;
                                            padding: 10px;
                                            border-radius: 8px;
                                            text-align: center;
                                        }}
                                        .email-body {{
                                            margin-top: 20px;
                                        }}
                                        .footer {{
                                            text-align: center;
                                            margin-top: 30px;
                                            font-size: 12px;
                                            color: #888;
                                        }}
                                        .footer a {{
                                            color: #0056b3;
                                            text-decoration: none;
                                        }}
                                    </style>
                                </head>
                                <body>
                                    <div class="email-container">
                                        <div class="email-header">
                                            <h2 style="color:white;">Important Notification from Intelligence Road Safety</h2>
                                        </div>
                                        <div class="email-body">
                                            <p><strong>New submissions from:</strong></p>
                                            <p><strong>State:</strong> {state}</p>
                                            <p><strong>District:</strong> {district}</p>
                                            <p><strong>Subdivision:</strong> {subdivision}</p>
                                            <br>
                                            <p>Details:</p>
                                            <ul>
                                                <li><strong>Message:</strong> {description}</li>
                                            </ul>
                                            <br>
                                            <p><strong>Thank you for your attention.</strong></p>
                                        </div>
                                        <div class="footer">
                                            <p>If you have any questions, feel free to <a href="mailto:info@roadsafety.com">contact us</a>.</p>
                                            <p>&copy; 2024 Intelligence Road Safety. All rights reserved.</p>
                                        </div>
                                    </div>
                                </body>
                            </html>
                            """

                            # Send email to the fetched list of emails
                            send_email_all(subject, body, email_list)
                            logging.info(f"Email sent to {email_list}")
                        else:
                            print("No emails found.")
                                
                        phone_numbers = get_phone_numbers(subdivision)
                        
                        if phone_numbers:
                            # Prepend +91 (India country code) to each phone number if it doesn't already have it
                            phone_numbers = ['+91' + num if not num.startswith('+') else num for num in phone_numbers]
                            send_sms = True

                    if send_sms:
                        logging.info("Sending SMS to users...")
                        # Construct the message body
                        """message_body = f"Message from Intelligence Road Safety: New submissions from {state}, {district}, {subdivision}" """

                        for number in phone_numbers:
                            # Send message to each phone number
                            """send_message(message_body, number)"""
                            logging.info(f"Message sent to {number}")
                else:
                    logging.info("No SMS sent.")

                    
                # Cleanup temporary directories
                shutil.rmtree(annotation_dir)
                shutil.rmtree(temp_dir)
            else:
                logging.info("No files with detections to process. Skipping database insertion and Google Drive upload.")


        # Start the background thread for processing
        threading.Thread(target=background_task).start()

        # Respond immediately with 200 OK after starting background processing
        return jsonify({
            "status": "success",
            "message": "File received successfully. Processing will be done in the background."
        }), 200

    except Exception as e:
        logging.error(f"Error in upload endpoint: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



def get_emails(subdivision=None):
    connection = None
    cursor = None
    emails = set()

    try:
        # Connect to the database using psycopg2
        connection = get_db_connection()
        cursor = connection.cursor()

        # Query the admin_login table for emails
        query_admin = "SELECT email FROM admin_login;"
        cursor.execute(query_admin)
        rows = cursor.fetchall()
        emails.update([row[0] for row in rows])

        # Query driver_login for emails based on subdivision if provided
        if subdivision:
            query_driver = "SELECT email FROM driver_login WHERE subdivision = %s;"
            cursor.execute(query_driver, (subdivision,))
        else:
            query_driver = "SELECT email FROM driver_login;"
            cursor.execute(query_driver)

        rows = cursor.fetchall()
        emails.update([row[0] for row in rows])

        # Query user_login_success for emails based on subdivision if provided
        if subdivision:
            query_user = "SELECT email FROM user_login_success WHERE subdivision = %s;"
            cursor.execute(query_user, (subdivision,))
        else:
            query_user = "SELECT email FROM user_login_success;"
            cursor.execute(query_user)

        rows = cursor.fetchall()
        emails.update([row[0] for row in rows])

    except Exception as e:
        logging.error(f"Error fetching emails: {e}")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return list(emails)

def send_email_all(subject, body, recipients):
    """Send email to a list of recipients using Flask-Mail."""
    with app.app_context():
        for email in recipients:
            try:
                msg = Message(subject, recipients=[email])
                msg.html = body
                mail.send(msg)
                logging.info(f"Email sent to {email}")
            except Exception as e:
                logging.error(f"Error sending email to {email}: {e}")


def send_message(message_body,to_number):
    # Twilio credentials
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_number = os.getenv('TWILIO_FROM_NUMBER')

    # Initialize Twilio client
    client = Client(account_sid, auth_token)

    # Send message
    message = client.messages.create(
        body=message_body,
        from_=from_number,
        to=to_number
    )

    logging.info(f"Message sent with SID: {message.sid}")


def get_phone_numbers(subdivision=None):
    connection = None
    cursor = None
    phone_numbers = set()  # Use a set to avoid duplicates

    try:
        # Use the get_db_connection function to get the connection
        connection = get_db_connection()
        cursor = connection.cursor()

        # Always fetch phone numbers from admin_login
        query_admin = """
        SELECT phone FROM admin_login;
        """
        cursor.execute(query_admin)
        rows = cursor.fetchall()
        phone_numbers.update([row[0] for row in rows])  # Add to set to avoid duplicates

        # If subdivision is provided, query driver_login based on the subdivision
        if subdivision:
            query_driver = """
            SELECT phone FROM driver_login
            WHERE subdivision = %s;
            """
            cursor.execute(query_driver, (subdivision,))
        else:
            query_driver = """
            SELECT phone FROM driver_login;
            """
            cursor.execute(query_driver)

        # Fetch phone numbers from driver_login
        rows = cursor.fetchall()
        phone_numbers.update([row[0] for row in rows])  # Add to set to avoid duplicates

        # If subdivision is provided, query user_login_success based on the subdivision
        if subdivision:
            query_user = """
            SELECT phone FROM user_login_success
            WHERE subdivision = %s;
            """
            cursor.execute(query_user, (subdivision,))
        else:
            query_user = """
            SELECT phone FROM user_login_success;
            """
            cursor.execute(query_user)

        # Fetch phone numbers from user_login_success
        rows = cursor.fetchall()
        phone_numbers.update([row[0] for row in rows])  # Add to set to avoid duplicates

    except Exception as e:
        logging.error(f"Error fetching phone numbers: {e}")

    finally:
        # Close cursor and connection if they were successfully created
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    # Convert the set back to a list before returning
    return list(phone_numbers)

if __name__ == '__main__':
    thread = Thread(target=background_task)
    thread.daemon = True
    thread.start()
    socketio.run(app, debug=True, host='0.0.0.0')
