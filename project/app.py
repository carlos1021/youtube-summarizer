from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import requests
import uuid
import numpy as np
from googleapiclient.discovery import build
from openai import OpenAI
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain_core.prompts import ChatPromptTemplate

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
llm = ChatOpenAI(model=MODEL)
API_KEY = os.getenv('API_KEY')
TRANSCRIPT_IO_API_TOKEN = os.getenv('TRANSCRIPT_IO_API_TOKEN')
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

print("✅ Flask app started and environment variables loaded.")

# In-memory session store for transcript chunks and embeddings.
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
        print("✅ Transcript successfully retrieved.")
        return response.json()
    else:
        print(f"❌ Transcript fetch failed: {response.status_code} - {response.text}")
        return None

def grab_transcript_text(io_response):
    try:
        print("🔍 Extracting transcript text...")
        tracks = io_response[0].get('tracks', [])
        if not tracks:
            print("⚠️ No tracks found in response.")
            return None
        transcript_entries = tracks[0].get('transcript', [])
        print(f"✅ Extracted {len(transcript_entries)} transcript segments.")
        return ' '.join([entry['text'] for entry in transcript_entries])
    except Exception as e:
        print(f"❌ Error processing transcript response: {e}")
        return None

def build_session_data(transcript_text, session_id, video_url):
    print(f"💾 Building session data for session: {session_id}")
    # Split the transcript into overlapping chunks without truncating the data.
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    text_chunks = text_splitter.split_text(transcript_text)
    print(f"📚 Split transcript into {len(text_chunks)} chunks.")

    # Precompute embeddings for each chunk.
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        encode_kwargs={'normalize_embeddings': True}
    )
    chunk_embeddings = embeddings.embed_documents(text_chunks)
    # Save the chunks and their embeddings in the session store.
    sessions[session_id] = {
        "video_url": video_url,
        "transcript_text": transcript_text,
        "chunks": [{"text": chunk, "embedding": emb} for chunk, emb in zip(text_chunks, chunk_embeddings)]
    }
    print("✅ Session data built and stored.")
    return session_id

def ask_question(session_id, question):
    print(f"🤖 Answering question for session: {session_id} | Question: {question}")
    session_data = sessions.get(session_id)
    if not session_data:
        print("❌ Session data not found.")
        return "Session not found. Please build the vectorstore first."

    # Get the stored chunks and compute the query embedding.
    chunks = session_data["chunks"]
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        encode_kwargs={'normalize_embeddings': True}
    )
    query_embedding = embeddings.embed_query(question)
    
    # Compute cosine similarity (dot product since embeddings are normalized).
    similarities = []
    for chunk in chunks:
        sim = np.dot(query_embedding, chunk["embedding"])
        similarities.append(sim)
    
    # Retrieve top 3 most similar chunks.
    top_indices = np.argsort(similarities)[-3:][::-1]
    selected_chunks = [chunks[i]["text"] for i in top_indices]
    context = "\n\n".join(selected_chunks)
    print("✅ Retrieved context from transcript.")

    # Use the context to build a prompt for the language model.
    template = """
You are an expert gaming assistant helping users understand video game mechanics. You answer questions briefly, and concisely, only providing necessary information to user's query.
Answer the question using the transcript context below:

<context>
{context}
</context>

Question: {input}
"""
    prompt = ChatPromptTemplate.from_template(template)
    chain = LLMChain(llm=llm, prompt=prompt)
    answer = chain.run(input=question, context=context)
    print("✅ Answer generated.")
    return answer

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
            return jsonify({'error': 'Transcript not available'}), 404

        transcript_text = grab_transcript_text(transcript_response)
        if not transcript_text:
            return jsonify({'error': 'Transcript parsing failed'}), 500

        session_id = str(uuid.uuid4())
        build_session_data(transcript_text, session_id, video_url)

        print("🎉 Session data built and session ID created.")
        return jsonify({'session_id': session_id, 'video_url': video_url})
    except Exception as e:
        app.logger.error(f"Error building session data: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

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
