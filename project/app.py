from flask import Flask, jsonify
from flask_cors import CORS
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from googleapiclient.discovery import build
import os
from openai import OpenAI
import time

'''
Flask is a web framework that allows programmers to build web applications
'''

#WSGI - Web Server Gateway Interface
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

    # Call the search.list method to retrieve search results matching the query
    search_response = youtube.search().list(
        q=query,
        part='id',
        type='video',
        maxResults=max_results
    ).execute()

    # Extract video IDs from the response
    video_ids = [item['id']['videoId'] for item in search_response['items']]

    return video_ids[0]

def youtube_transcript(video_id):
    return YouTubeTranscriptApi.get_transcript(video_id)

def chat_with_chatgpt(transcript):
	response = client.chat.completions.create(model=MODEL,
	    messages=[
				{
					"role": "system",
					"content": "You are an expert assistant at writing comprehensive summaries of Youtube video transcripts in less than 100 words."
				}, 
				{
					"role": "user",
					"content": f"Generate a summary which discusses the main points of the following transcript: {transcript}"
				}
			])

	message = response.choices[0].message
	return message

def grab_transcript(raw_transcript):
    filtered_transcript = []
    for dictionary in raw_transcript:
        filtered_transcript.append(dictionary['text'])
    filtered_transcript = ' '.join(filtered_transcript)
    return filtered_transcript
    
@app.route('/get_transcript')
def grab_results():
    transcript = youtube_transcript(search_videos('How to play top lane in league of legends', max_results=1, order='date'))
    return jsonify({'transcript':grab_transcript(transcript)})

if __name__ == "__main__":
    app.run(host = "0.0.0.0", port = 3000)