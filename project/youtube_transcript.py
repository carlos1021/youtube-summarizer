"""CODING EXAMPLE: WORKING WITH YOUTUBE API"""

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from googleapiclient.discovery import build
import os
from openai import OpenAI
import time

'''
NOTES:

Proposed Architecture: Video ID -> Transcript -> Preprocessing -> ChatGPT

Example URL: https://www.youtube.com/watch?v=VIDEO_ID_HERE
'''

client = OpenAI(api_key='...')
MODEL = "gpt-4o-mini"
# client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
# API_KEY = os.getenv('API_KEY')
API_KEY = 'AIzaSyBHS8clojUyrHriGSWsegpPiqW_O5-VXhs'
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

    return video_ids

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

# Example usage
if __name__ == "__main__":
    query = input("What video would you like a transcript for?")
    video_ids = search_videos(query)
    transcript = youtube_transcript(video_ids[0])
    # print("Video ID:", video_ids)
    # print(f"Checking that video id is correct: {video_ids[0] == 'L2xo8EmzJuw'}")
    # print(f"Transcripts: {transcript}")
    # final_output = chat_with_chatgpt(transcript)
    print(f'Transcript: {transcript}')
    # print(f"""Here is a comprehensive summary of the transcript: {final_output}""")
