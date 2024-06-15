from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import threading
import time
import pytz
import logging
import os

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

# Define the model for daily counts
class TomatoCount(db.Model):
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

# Lock for thread-safe counter updates
counter_lock = threading.Lock()

def reset_counters():
    global counters
    with app.app_context():
        while True:
            now = datetime.now(local_tz)
            logging.info(f"Current date: {now.date()}")
            logging.info(f"Last reset: {counters['last_reset']}")
            
            if now.date() != counters['last_reset']:
                with counter_lock:
                    try:
                        # Save the counts to the database before resetting
                        new_record = TomatoCount(
                            date=counters['last_reset'],
                            fresh_count=counters['fresh'],
                            rotten_count=counters['rotten']
                        )
                        db.session.add(new_record)
                        db.session.commit()
                        
                        # Reset the counters
                        counters['fresh'] = 0
                        counters['rotten'] = 0
                        counters['last_reset'] = now.date()
                        logging.info("Counters have been reset.")
                    except Exception as e:
                        db.session.rollback()
                        logging.error(f"Failed to reset counters: {e}")
            else:
                logging.info("No reset needed.")
            
            # Sleep for a short period to reduce CPU usage
            time.sleep(5)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/update', methods=['POST'])
def update_counter():
    global counters
    detection_result = request.json  # {'type': 'fresh'} or {'type': 'rotten'}
    
    with counter_lock:
        if detection_result['type'] == 'fresh':
            counters['fresh'] += 1
        elif detection_result['type'] == 'rotten':
            counters['rotten'] += 1

    return jsonify(success=True)

@app.route('/count', methods=['GET'])
def get_count():
    global counters
    return jsonify(counters)

@app.route('/history', methods=['GET'])
def get_history():
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

if __name__ == '__main__':
    # Ensure the database and table are created
    with app.app_context():
        db.create_all()

    # Start the reset counters thread
    reset_thread = threading.Thread(target=reset_counters, daemon=True)
    reset_thread.start()

    # Run the Flask application
    app.run(host='0.0.0.0', port=5000)
