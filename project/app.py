from flask import Flask, jsonify
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

client = OpenAI(api_key='...')
MODEL = "gpt-4o-mini"

API_KEY = '...'
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

@app.route("/grab_transcript", methods=['GET'])
def grab_transcript():
    transcript = []
    raw_transcript = youtube_transcript(search_videos('What are the best keybinds on csgo?')[0])
    for dictionary in raw_transcript:
        transcript.append(dictionary['text'])
    chat_gpt_response = chat_with_chatgpt(transcript)
    return chat_gpt_response.content
    


if __name__ == "__main__":
    app.run(debug = True, host = "0.0.0.0", port = 3000)





# print(chat_with_chatgpt('Hello World!'))
# """
# ChatCompletionMessage(content='The transcript simply begins with the phrase "Hello World!" 
#                             which is often used as a basic expression or introduction in programming and technology-related contexts. 
#                             It signifies the starting point for many coding tutorials and serves as a friendly greeting to viewers. 
#                             The brevity of the transcript suggests it sets the stage for further content.', 
# 					    refusal=None, 
# 						role='assistant', 
# 						function_call=None, 
# 						tool_calls=None)
# """



'''
user pass in query (best opening move in chess)

query gets sent to YouTube API -> transcript 

transcript -> model (ChatGPT) -> summarize text
'''