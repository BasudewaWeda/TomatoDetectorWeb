from flask import Flask, request, jsonify, render_template, send_file
from flask_migrate import Migrate, upgrade
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import tempfile
import mimetypes
import threading
import time
import pytz
import logging
import os
import requests

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Configure the database URI
DATABASE_USER = os.environ.get("POSTGRES_USER")
DATABASE_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
DATABASE_HOST = os.environ.get("POSTGRES_HOST")
DATABASE_DATABASE = os.environ.get("POSTGRES_DATABASE")
app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:5432/{DATABASE_DATABASE}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Define the model for daily counts
class TomatoCount(db.Model):
    __tablename__ = 'tomato_count'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    fresh_count = db.Column(db.Integer, nullable=False)
    rotten_count = db.Column(db.Integer, nullable=False)

# Define Timezone
timezone = 'Asia/Makassar'
local_tz = pytz.timezone(timezone)

# Initialize counters
time_init = datetime.now(local_tz)
counters = {
    'fresh': 0,
    'rotten': 0,
    'last_reset': time_init.date() # - timedelta(days=1)
}

current_image = None

# Lock for thread-safe counter updates
# counter_lock = threading.Lock()

def reset_counters():
    global counters
    now = datetime.now(local_tz)

    # with app.app_context():
    #     while True:
    try:
        # Retrieve the existing record (if any)
        # tomato_record = TomatoCount.query.get(now.date())
        tomato_record = TomatoCount.query.filter_by(date=now.date()).first()
        # Update counts regardless of day change
        if tomato_record:
            tomato_record.fresh_count += counters['fresh']
            tomato_record.rotten_count += counters['rotten']
            counters['fresh'] = 0
            counters['rotten'] = 0
        else:
            # Create a new record if none exists
            counters = {'fresh': 0, 'rotten': 0, 'last_reset': now.date()}
            tomato_record = TomatoCount(date=now.date(),
                                         fresh_count=0,
                                         rotten_count=0)
            db.session.add(tomato_record)
        # Save the record
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to reset counters: {e}")
    
    time.sleep(5)

def setup_database():
    with app.app_context():
        upgrade()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/update_text', methods=['POST'])
def update_counter_text():
    global counters
    detection_result = request.json  # {'type': 'fresh'} or {'type': 'rotten'}
    
    if detection_result['type'] == 'fresh':
        counters['fresh'] += 1
    elif detection_result['type'] == 'rotten':
        counters['rotten'] += 1

    reset_counters()

    return jsonify(success=True)

@app.route('/update', methods=['POST'])
def update_counter():
    global counters
    # if 'image' not in request.files:
    #     return 'No image file uploaded!', 400  # Bad request response

    # fresh_count = 0
    # rotten_count = 0
    # class_response = 0

    # image = request.files['image']
    # files = {'image': image}

    # response = requests.post('https://basudewaweda-tomatodetectortest.hf.space/predict', files=files)

    # if response.status_code == 200:
    #     response_json = response.json()
    #     fresh_count = response_json.get('fresh')
    #     rotten_count = response_json.get('rotten')

    #     if fresh_count >= rotten_count:
    #         class_response = 1 # 1 = fresh
    #     else:
    #         class_response = 0 # 0 = rotten

    #     counters['fresh'] += response_json.get('fresh')
    #     counters['rotten'] += response_json.get('rotten')

    #     response_data = {
    #         'class': class_response
    #     }

    #     reset_counters()

    #     return jsonify(response_data), 200
    # else:
    #     return "Failed to do inference", 404
    
    try:
        detection_result = request.get_json()

        fresh_count = detection_result.get('fresh')
        rotten_count = detection_result.get('rotten')

        counters['fresh'] += fresh_count
        counters['rotten'] += rotten_count

        reset_counters()

        return "Successfully processed", 200
    except:
        return "Something went wrong", 404
    
# @app.route('/upload-img', methods=['POST'])
# def upload_img():
#     global current_image

#     if 'image' not in request.files:
#         return 'No image file uploaded!', 400  # Bad request response

#     current_image = request.files['image']

#     return 'Successfully uploaded image', 200

# @app.route('/get-img', methods=['GET'])
# def get_img():
#     global current_image

#     if not current_image:
#         return 'No image available', 200
    
#     # image_data = {
#     #     'image': current_image
#     # }

#     # return jsonify(image_data), 200
#     current_image.seek(0)
#     return send_file(current_image, mimetype=current_image.content_type)

# UPLOAD_FOLDER = 'uploads'
# ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

# # Ensure upload folder exists
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# def allowed_file(filename):
#     return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# @app.route('/upload-img', methods=['POST'])
# def upload_img():
#     global current_image
    
#     # Check if image file is present in the request
#     if 'image' not in request.files:
#         return 'No image file uploaded!', 400  # Bad request response

#     file = request.files['image']

#     # Validate file extension
#     if file.filename == '' or not allowed_file(file.filename):
#         return 'Invalid file format', 400

#     # Save the uploaded file
#     filename = secure_filename(file.filename)
#     file_path = os.path.join(UPLOAD_FOLDER, filename)
#     file.save(file_path)

#     # Delete existing image if it exists
#     if current_image:
#         try:
#             os.remove(os.path.join(UPLOAD_FOLDER, current_image))
#         except FileNotFoundError:
#             pass

#     # Update current_image variable with the new filename
#     current_image = filename

#     return 'Successfully uploaded image', 200

# @app.route('/get-img', methods=['GET'])
# def get_img():
#     global current_image

#     if not current_image:
#         return 'No image available', 404

#     try:
#         return send_file(
#             os.path.join(UPLOAD_FOLDER, current_image),
#             mimetype='image/jpeg'  # Adjust mimetype based on your image type
#         )
#     except Exception as e:
#         return str(e), 500

tempdir = tempfile.TemporaryDirectory()

# Allowed file extensions
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload-img', methods=['POST'])
def upload_img():
    if 'image' not in request.files:
        return 'No image file uploaded!', 400

    file = request.files['image']

    if file.filename == '' or not allowed_file(file.filename):
        return 'Invalid file format', 400

    # Save the uploaded file to a temporary directory
    filename = secure_filename(file.filename)
    file_path = os.path.join(tempdir.name, filename)
    file.save(file_path)

    return 'Successfully uploaded image', 200

@app.route('/get-img', methods=['GET'])
def get_img():
    try:
        # List files in the temporary directory
        files = [f for f in os.listdir(tempdir.name) if os.path.isfile(os.path.join(tempdir.name, f))]
        
        if not files:
            return 'No image available', 404

        # Find the most recently uploaded file
        latest_file = max(files, key=lambda f: os.path.getmtime(os.path.join(tempdir.name, f)))
        file_path = os.path.join(tempdir.name, latest_file)

        # Determine the MIME type of the file
        mime_type, _ = mimetypes.guess_type(file_path)

        return send_file(file_path, mimetype=mime_type)
    except Exception as e:
        return str(e), 500

@app.route('/count', methods=['GET'])
def get_count():
    now = datetime.now(local_tz)
    tomato_record = TomatoCount.query.filter_by(date=now.date()).first()

    data = {
        'fresh': tomato_record.fresh_count if tomato_record else 0,
        'rotten': tomato_record.rotten_count if tomato_record else 0
    }

    return jsonify(data)

@app.route('/history', methods=['GET'])
def get_history():
    try:
        days = request.args.get('days', default=7, type=int)
        end_date = datetime.now(local_tz).date()
        start_date = end_date - timedelta(days=days)
        
        records = TomatoCount.query.filter(TomatoCount.date.between(start_date, end_date)).all()
        
        history = {
            'dates': [record.date.strftime('%Y-%m-%d') for record in records],
            'fresh_counts': [record.fresh_count for record in records],
            'rotten_counts': [record.rotten_count for record in records]
        }
        
        return jsonify(history)
    except Exception as e:
        logging.error(f"Error occurred in /history route: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

if __name__ == '__main__':
    setup_database()
    # Ensure the database and table are created
    with app.app_context():
        db.create_all()

    # Start the reset counters thread
    reset_thread = threading.Thread(target=reset_counters, daemon=True)
    reset_thread.start()

    # Run the Flask application
    app.run()
