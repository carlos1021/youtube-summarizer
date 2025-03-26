from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import requests
import uuid
from googleapiclient.discovery import build
from openai import OpenAI
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from langchain.chat_models import ChatOpenAI
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_retrieval_chain
from langchain.schema import Document

load_dotenv()

app = Flask(__name__)

CORS(app, origins=[
    'https://summarizer-c3229.firebaseapp.com',
    'https://summarizer-c3229.web.app',
    'http://localhost:6760'
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

print("Loaded API_KEY:", API_KEY)
print("Loaded TRANSCRIPT_IO_API_TOKEN:", TRANSCRIPT_IO_API_TOKEN)

def search_videos(query, max_results=1, order='relevance'):
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
        return None, None

    video_id = items[0]['id']['videoId']
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    return video_id, video_url

def fetch_transcript_from_io(video_id):
    url = "https://www.youtube-transcript.io/api/transcripts"
    headers = {
        "Authorization": f"Basic {TRANSCRIPT_IO_API_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {"ids": [video_id]}

    print(f"Sending request to youtube-transcript.io with video_id: {video_id}")
    response = requests.post(url, headers=headers, json=data)
    print("Transcript IO response status:", response.status_code)

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
        return ' '.join([entry['text'] for entry in transcript_entries])
    except Exception as e:
        print(f"Error processing transcript response: {e}")
        return None

def build_vectorstore(transcript_text, session_id):
    document = [Document(page_content=transcript_text)]
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    text_chunks = text_splitter.split_documents(document)

    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        encode_kwargs={'normalize_embeddings': True}
    )

    vectorstore = FAISS.from_documents(text_chunks, embeddings)
    vectorstore.save_local(f'vectorstores/{session_id}')
    return session_id

def ask_question(session_id, question):
    vectorstore = FAISS.load_local(f'vectorstores/{session_id}', HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        encode_kwargs={'normalize_embeddings': True}
    ))
    retriever = vectorstore.as_retriever()

    template = """
    You are an expert gaming assistant helping users understand video game mechanics.
    Answer the question using the transcript context below:

    <context>
    {context}
    </context>

    Question: {input}
    """
    prompt = ChatPromptTemplate.from_template(template)
    doc_chain = create_stuff_documents_chain(llm, prompt)
    chain = create_retrieval_chain(retriever, doc_chain)
    response = chain.invoke({"input": question})
    return response["answer"]

@app.route('/build_vectorstore', methods=['POST'])
def build_vectorstore_endpoint():
    try:
        data = request.get_json()
        topic = data.get('topic', '')
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
        build_vectorstore(transcript_text, session_id)

        return jsonify({'session_id': session_id, 'video_url': video_url})
    except Exception as e:
        app.logger.error(f"Error building vectorstore: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        question = data.get('question')

        if not session_id or not question:
            return jsonify({'error': 'session_id and question are required'}), 400

        answer = ask_question(session_id, question)
        return jsonify({'answer': answer})
    except Exception as e:
        app.logger.error(f"Error answering question: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == "__main__":
    os.makedirs('vectorstores', exist_ok=True)
    app.run(host="0.0.0.0", port=8000)
