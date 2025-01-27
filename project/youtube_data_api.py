from flask import Flask, jsonify, request
from flask_cors import CORS
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from io import StringIO
from openai import OpenAI
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from langchain.chat_models import ChatOpenAI
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_retrieval_chain
from langchain.schema import Document
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import json
load_dotenv()
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
app = Flask(__name__)

CORS(app, origins=[
    'https://summarizer-c3229.firebaseapp.com',
    'https://summarizer-c3229.web.app',
    'https://youtube-summarizer-vi8d.onrender.com'
],
methods=["GET", "POST", "OPTIONS"],
allow_headers=["Content-Type"])

MODEL = "gpt-4"
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
llm = ChatOpenAI(model=MODEL)
API_KEY = os.getenv('API_KEY')
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

def get_authenticated_service():
    """Authenticate and return the YouTube API service."""
    creds = None
    # Load credentials from file if they exist
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If no valid credentials, prompt the user to log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Load OAuth credentials from environment variable
            client_secret = os.getenv('CLIENT_SECRET_JSON')
            if not client_secret:
                raise ValueError("CLIENT_SECRET_JSON environment variable is not set.")
            
            client_config = json.loads(client_secret)
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

            # Set redirect_uri based on environment
            if os.getenv('ENVIRONMENT') == 'production':
                redirect_uri = 'https://youtube-summarizer-vi8d.onrender.com/oauth2callback'
            else:
                redirect_uri = 'http://localhost:7000/oauth2callback'

            creds = flow.run_local_server(port=7000, redirect_uri=redirect_uri)
        
        # Save the credentials for future use
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('youtube', 'v3', credentials=creds)

def search_videos(query, max_results=5, order='date'):
    print('called search_videos function')
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
    search_response = youtube.search().list(
        q=query,
        part='id',
        type='video',
        maxResults=max_results
    ).execute()

    video_ids = [item['id']['videoId'] for item in search_response['items']]
    return video_ids if video_ids else None

def get_captions(video_id):
    print('called get_captions function')
    youtube = get_authenticated_service()
    captions = youtube.captions().list(
        part='snippet',
        videoId=video_id
    ).execute()

    if not captions['items']:
        return None

    # Get the first available caption track (usually the default one)
    caption_id = captions['items'][0]['id']
    caption_download = youtube.captions().download(
        id=caption_id,
        tfmt='srt'  # or 'vtt' for WebVTT format
    ).execute()

    # Parse the caption content
    caption_content = caption_download.decode('utf-8')
    return caption_content

def parse_captions(caption_content):
    """
    Parse captions in .srt or .vtt format into a plain text transcript.
    """
    print('called parse_captions function')
    transcript = []
    for line in caption_content.splitlines():
        if not line.strip().isdigit() and '-->' not in line:  # Skip timestamps and line numbers
            transcript.append(line.strip())
    return ' '.join(transcript)

def grab_transcript(raw_transcript):
    return ' '.join([item['text'] for item in raw_transcript])

def rag_system(query, transcript):
    """
    Invoke a conversation with ChatGPT using the Python LangChain implementation.
    Input: query (string) from the user 
    Output: augmented response (string) from LLM
    """
    document = [Document(page_content=transcript)]
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    text_chunks = text_splitter.split_documents(document)

    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        encode_kwargs={'normalize_embeddings': True}
    )

    vectorstore = FAISS.from_documents(text_chunks, embeddings)
    vectorstore.save_local('vectorstore.db')
    retriever = vectorstore.as_retriever()

    template = """
    You are an expert assistant at writing comprehensive summaries of Youtube video transcripts in less than 300 words.
    Generate a summary which discusses the main points of the following transcript.
    Use the provided context only to answer the following question(s):

    <context>
    {context}
    </context>

    Question: {input}
    """

    prompt = ChatPromptTemplate.from_template(template)
    doc_chain = create_stuff_documents_chain(llm, prompt)
    chain = create_retrieval_chain(retriever, doc_chain)
    questions = {query}
    chunked_text = ''
    for question in questions:
        response = chain.invoke({"input": question})
        if response["answer"]:
            print(f"Question: {question}\nAnswer: {response['answer']}\n\n")
            chunked_text += f"{question} {response['answer']}"
        else:
            print(f"Question: {question}\nAnswer: No Information\n\n")
            chunked_text += f"{question}, 'No Information\n\n\n'"
    return chunked_text

@app.route('/', methods=['OPTIONS'])
def handle_preflight():
    return '', 200

@app.route('/get_transcript', methods=['POST'])
def grab_results():
    try:
        data = request.get_json()
        query = data.get('query', '')
        print(query)
        if not query:
            return jsonify({'error': 'Query is required'}), 400

        video_ids = search_videos(query)
        if not video_ids:
            return jsonify({'error': 'No videos found for the query'}), 404

        # Use the first video ID for simplicity
        video_id = video_ids[0]
        captions = get_captions(video_id)
        if not captions:
            return jsonify({'error': f'Captions unavailable for video ID: {video_id}'}), 404

        transcript = parse_captions(captions)
        return jsonify({'transcript': rag_system(query, transcript)})
    except Exception as e:
        app.logger.error(f"Error processing request: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000, debug=True)