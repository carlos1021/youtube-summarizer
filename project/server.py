from flask import Flask, jsonify
from flask_cors import CORS
import random


app = Flask(__name__)

CORS(app, origins=[
    'summarizer-c3229.firebaseapp.com',
    'summarizer-c3229.web.app',
    'http://localhost:8000'
],
methods=["GET", "POST", "OPTIONS"],
allow_headers=["Content-Type"])

@app.route('/generate_random_number')
def generate_random_number():
    return jsonify({'random_number': random.randint(1, 1000)})

if __name__ == '__main__':
    app.run()

