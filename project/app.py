from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from youtube_transcript_api import YouTubeTranscriptApi
from googleapiclient.discovery import build
from openai import OpenAI

app = Flask(__name__)

CORS(app, origins=[
    'https://summarizer-c3229.firebaseapp.com',
    'https://summarizer-c3229.web.app',
    'http://localhost:8000'
],
methods=["GET", "POST", "OPTIONS"],
allow_headers=["Content-Type"])

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
MODEL = "gpt-4o-mini"

API_KEY = os.getenv('API_KEY')
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

def search_videos(query, max_results=1, order='date'):
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
    search_response = youtube.search().list(
        q=query,
        part='id',
        type='video',
        maxResults=max_results
    ).execute()

    video_ids = [item['id']['videoId'] for item in search_response['items']]
    return video_ids[0] if video_ids else None

def youtube_transcript(video_id):
    return YouTubeTranscriptApi.get_transcript(video_id)

def grab_transcript(raw_transcript):
    return ' '.join([item['text'] for item in raw_transcript])

@app.route('/get_transcript', methods=['POST'])
def grab_results():
    data = request.get_json()
    query = data.get('query', '')

    if not query:
        return jsonify({'error': 'Query is required'}), 400

    try:
        video_id = search_videos(query)
        if not video_id:
            return jsonify({'error': 'No videos found for the query'}), 404

        transcript = youtube_transcript(video_id)
        return jsonify({'transcript': grab_transcript(transcript)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
