from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import requests
from googleapiclient.discovery import build
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

CORS(app, origins=[
    'https://summarizer-c3229.firebaseapp.com',
    'https://summarizer-c3229.web.app'
],
methods=["GET", "POST", "OPTIONS"],
allow_headers=["Content-Type"])

MODEL = "gpt-4o-mini"
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
API_KEY = os.getenv('API_KEY')
TRANSCRIPT_IO_API_TOKEN = os.getenv('TRANSCRIPT_IO_API_TOKEN')
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

print("Loaded API_KEY:", API_KEY)
print("Loaded TRANSCRIPT_IO_API_TOKEN:", TRANSCRIPT_IO_API_TOKEN)

def search_videos(query, max_results=5, order='date'):
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
    search_response = youtube.search().list(
        q=query,
        part='id',
        type='video',
        maxResults=max_results
    ).execute()

    video_ids = [item['id']['videoId'] for item in search_response['items']]
    print("Found video IDs:", video_ids)
    return video_ids if video_ids else None

def fetch_transcript_from_io(video_id):
    url = "https://www.youtube-transcript.io/api/transcripts"
    headers = {
        "Authorization": f"Basic {TRANSCRIPT_IO_API_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {"ids": [video_id]}

    print(f"Sending request to youtube-transcript.io with video_id: {video_id}")
    print("Headers:", headers)
    response = requests.post(url, headers=headers, json=data)
    print("Transcript IO response status:", response.status_code)
    print("Transcript IO response body:", response.text)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching transcript: {response.status_code} {response.text}")
        return None

def grab_transcript_text(io_response):
    try:
        tracks = io_response[0].get('tracks', [])
        if not tracks:
            print("No tracks found in transcript response")
            return None
        transcript_entries = tracks[0].get('transcript', [])
        print(f"Number of transcript entries: {len(transcript_entries)}")
        return ' '.join([entry['text'] for entry in transcript_entries])
    except Exception as e:
        print(f"Error processing transcript response: {e}")
        return None

@app.route('/get_transcript', methods=['POST'])
def grab_results():
    try:
        data = request.get_json()
        query = data.get('query', '')
        print("Received query:", query)

        if not query:
            return jsonify({'error': 'Query is required'}), 400

        video_ids = search_videos(query)
        if not video_ids:
            return jsonify({'error': 'No videos found for the query'}), 404

        transcript_response = fetch_transcript_from_io(video_ids[0])
        if not transcript_response:
            return jsonify({'error': f'Transcript unavailable for video ID: {video_ids[0]}'}), 404

        transcript_text = grab_transcript_text(transcript_response)
        if not transcript_text:
            return jsonify({'error': 'Transcript parsing failed'}), 500

        print("Successfully retrieved transcript.")
        return jsonify({'transcript': transcript_text})
    except Exception as e:
        app.logger.error(f"Error processing request: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
