from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import requests
import uuid
import json
from googleapiclient.discovery import build
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

CORS(app, origins=[
    'https://summarizertool-96202.firebaseapp.com',
    'https://summarizertool-96202.web.app'
],
methods=["GET", "POST", "OPTIONS"],
allow_headers=["Content-Type"])

MODEL = "gpt-4o-mini"
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
API_KEY = os.getenv('API_KEY')
TRANSCRIPT_IO_API_TOKEN = os.getenv('TRANSCRIPT_IO_API_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

print("✅ Flask app started and environment variables loaded.")

# In-memory session store for transcripts and conversation history
sessions = {}

def search_videos(query, max_results=1, order='relevance'):
    print(f"🔍 Searching YouTube for query: {query}")
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
    search_response = youtube.search().list(
        q=query,
        part='id,snippet',
        type='video',
        maxResults=max_results,
        order=order
    ).execute()

    items = search_response.get('items', [])
    if not items:
        print("❌ No search results returned from YouTube.")
        return None, None

    video_id = items[0]['id']['videoId']
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"✅ Found video: {video_url}")
    return video_id, video_url

def fetch_transcript_from_io(video_id):
    url = "https://www.youtube-transcript.io/api/transcripts"
    headers = {
        "Authorization": f"Basic {TRANSCRIPT_IO_API_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {"ids": [video_id]}

    print(f"📡 Requesting transcript for video ID: {video_id}")
    response = requests.post(url, headers=headers, json=data)
    print("🧾 Transcript IO response status:", response.status_code)

    if response.status_code == 200:
        response_data = response.json()
        print(f"Response data: {json.dumps(response_data)[:200]}...")  # Print first 200 chars of response
        
        # Check if we have valid data
        if not response_data or not isinstance(response_data, list) or len(response_data) == 0:
            print("❌ Empty or invalid response from transcript API")
            return None
            
        print("✅ Transcript successfully retrieved.")
        return response_data
    else:
        print(f"❌ Transcript fetch failed: {response.status_code} - {response.text}")
        return None

def grab_transcript_text(io_response):
    try:
        print("🔍 Extracting transcript text...")
        # Log the structure of the response for debugging
        print(f"Response structure: {type(io_response)}, length: {len(io_response) if isinstance(io_response, list) else 'not a list'}")
        
        # Handle different response structures
        if not io_response or not isinstance(io_response, list) or len(io_response) == 0:
            print("⚠️ Empty response array.")
            return None
            
        first_item = io_response[0]
        print(f"First item keys: {list(first_item.keys()) if isinstance(first_item, dict) else 'not a dict'}")
        
        # Try to get tracks from the response
        tracks = first_item.get('tracks', []) if isinstance(first_item, dict) else []
        video_id = first_item.get('id', '')
        
        if not tracks:
            # Try alternative structures - youtube-transcript-api might return differently
            transcript_entries = first_item.get('transcript', [])
            if transcript_entries:
                print(f"✅ Found transcript directly in response. {len(transcript_entries)} segments.")
                return ' '.join([entry['text'] for entry in transcript_entries])
                
            # If we still don't have tracks, try using youtube-transcript-api as fallback
            return None  # Return None to trigger fallback with the correct video_id
            
        transcript_entries = tracks[0].get('transcript', [])
        if not transcript_entries:
            print("⚠️ No transcript entries found in tracks.")
            return None  # Return None to trigger fallback with the correct video_id
            
        print(f"✅ Extracted {len(transcript_entries)} transcript segments.")
        return ' '.join([entry['text'] for entry in transcript_entries])
    except Exception as e:
        print(f"❌ Error processing transcript response: {e}")
        return None

def fetch_transcript_fallback(video_id):
    """Fallback method to fetch transcript using youtube-transcript-api directly"""
    try:
        # This is a placeholder for where you would implement a fallback method
        # For example, you could call youtube-transcript-api directly or use another service
        print("⚠️ Using fallback transcript method...")
        
        # Example: Make a direct request to another transcript API
        # For this example, I'll use a simple approach with direct YouTube link
        transcript_url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"🔍 Attempting to fetch transcript from: {transcript_url}")
        
        # Fallback to OpenAI for content extraction if needed
        system_msg = "You are a transcript extraction assistant. Your job is to help extract a synopsis of the video content."
        user_msg = f"Please watch this YouTube video and provide a detailed transcript or summary of its content: {transcript_url}. Focus only on the informational content."
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            max_tokens=1000
        )
        
        fallback_transcript = response.choices[0].message.content
        print("✅ Generated fallback transcript summary.")
        return fallback_transcript
    except Exception as e:
        print(f"❌ Error in fallback transcript method: {e}")
        return "No transcript available for this video."

def build_session_data(transcript_text, session_id, video_url):
    print(f"💾 Building session data for session: {session_id}")
    # Store the full transcript text in the session
    sessions[session_id] = {
        "video_url": video_url,
        "transcript_text": transcript_text,
        "messages": []
    }
    print("✅ Session data built and stored.")
    return session_id

def ask_question(session_id, question):
    print(f"🤖 Answering question for session: {session_id} | Question: {question}")
    session_data = sessions.get(session_id)
    if not session_data:
        print("❌ Session data not found.")
        return "Session not found. Please build a session first."

    # Get the transcript and prepare the messages
    transcript_text = session_data["transcript_text"]
    
    # Update the session messages with user question
    session_data["messages"].append({"role": "user", "content": question})
    
    # Prepare messages to send to the model
    messages_to_send = [
        {"role": "system", "content": "You are an expert gaming assistant helping users understand video game mechanics. You answer questions briefly, and concisely, only providing necessary information to user's query."},
        {"role": "user", "content": f"Here is a YouTube video transcript:\n\n{transcript_text}\n\nPlease answer the following question about this content: {question}"}
    ]
    
    # Include previous conversation history if it exists
    if len(session_data["messages"]) > 2:
        # Add only the last few exchanges to maintain context without exceeding token limits
        prev_messages = session_data["messages"][:-1]  # Exclude the current question
        for msg in prev_messages[-4:]:  # Include up to 4 previous messages
            messages_to_send.append(msg)
        
        # Add the current question again at the end
        messages_to_send.append({"role": "user", "content": question})
    
    try:
        # Call OpenRouter API
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://youtube-summarizer.com",
                "X-Title": "YouTube Summarizer",
            },
            json={
                "model": "google/gemini-2.5-pro-exp-03-25:free",  # High context window model
                "messages": messages_to_send,
                "temperature": 0.1,
                "max_tokens": 2000
            }
        )
        
        if response.status_code != 200:
            print(f"Error from OpenRouter: {response.text}")
            return f"API Error: {response.status_code}"
        
        result = response.json()
        print(f"API Response received from OpenRouter")
        
        if 'choices' not in result or not result['choices'] or 'message' not in result['choices'][0]:
            print(f"Unexpected API response format")
            return "Unexpected API response format"
            
        assistant_message = result['choices'][0]['message']['content']
        
        # Add assistant response to history
        session_data["messages"].append({"role": "assistant", "content": assistant_message})
        
        return assistant_message
        
    except Exception as e:
        print(f"Error calling OpenRouter API: {str(e)}")
        return f"Error: {str(e)}"

@app.route('/build_vectorstore', methods=['POST'])
def build_vectorstore_endpoint():
    try:
        print("📥 /build_vectorstore endpoint hit")
        data = request.get_json()
        topic = data.get('topic', '')
        print("📝 Topic received:", topic)
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400

        video_id, video_url = search_videos(topic)
        if not video_id:
            return jsonify({'error': 'No video found for that topic'}), 404

        transcript_response = fetch_transcript_from_io(video_id)
        if not transcript_response:
            print(f"⚠️ Could not retrieve transcript from primary API, trying fallback with video ID: {video_id}")
            # Direct fallback if the API call failed entirely
            transcript_text = fetch_transcript_fallback(video_id)
            if not transcript_text:
                return jsonify({'error': 'Transcript not available'}), 404
        else:
            transcript_text = grab_transcript_text(transcript_response)
            if not transcript_text:
                print(f"⚠️ Could not parse transcript, trying fallback with video ID: {video_id}")
                transcript_text = fetch_transcript_fallback(video_id)
                if not transcript_text:
                    return jsonify({'error': 'Transcript parsing failed'}), 500

        session_id = str(uuid.uuid4())
        build_session_data(transcript_text, session_id, video_url)

        print("🎉 Session data built and session ID created.")
        return jsonify({'session_id': session_id, 'video_url': video_url})
    except Exception as e:
        print(f"❌ Error building session data: {str(e)}")
        app.logger.error(f"Error building session data: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/ask', methods=['POST'])
def ask():
    try:
        print("📥 /ask endpoint hit")
        data = request.get_json()
        session_id = data.get('session_id')
        question = data.get('question')
        print(f"❓ Q: {question} | Session: {session_id}")

        if not session_id or not question:
            return jsonify({'error': 'session_id and question are required'}), 400

        answer = ask_question(session_id, question)
        return jsonify({'answer': answer})
    except Exception as e:
        app.logger.error(f"Error answering question: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
