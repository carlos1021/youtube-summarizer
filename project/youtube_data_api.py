import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain.embeddings.huggingface import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from langchain.chat_models import ChatOpenAI
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain.prompts.chat import ChatPromptTemplate
import openai

# Load your OPENAI_API_KEY from environment or however you prefer
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
CORS(app, origins=["*"], allow_headers=["Content-Type"], methods=["GET", "POST", "OPTIONS"])

# OAuth-related global data
CLIENT_SECRET_PATH = "client_secret.json"  # Where we'll store the user's uploaded JSON
TOKEN_PATH = "token.json"                  # Where we'll store the user's token

SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
MODEL = "gpt-4"

# Set your own redirect URI. It must match what's set in your Google Cloud OAuth client.
REDIRECT_URI = "https://<YOUR_DOMAIN_OR_LOCALHOST>/oauth2callback"

# LangChain resources
llm = ChatOpenAI(model=MODEL)


def is_client_secret_uploaded():
    """Check if the user has already uploaded client_secret.json."""
    return os.path.exists(CLIENT_SECRET_PATH)


def load_client_secret():
    """Load the OAuth client secret from disk."""
    if not is_client_secret_uploaded():
        raise Exception("Client secret JSON not found. Please upload first.")
    with open(CLIENT_SECRET_PATH, "r") as f:
        return json.load(f)


def get_flow():
    """
    Create an OAuth flow instance from our stored client_secret.json.
    """
    client_config = load_client_secret()
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    return flow


@app.route('/upload_client_secret', methods=['POST'])
def upload_client_secret():
    """
    Endpoint where user uploads the client secret JSON file.
    Expecting multipart/form-data with a file input named 'client_secret'.
    """
    try:
        if 'client_secret' not in request.files:
            return jsonify({"error": "No file part in the request"}), 400

        file = request.files['client_secret']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        # Save the JSON file on the server
        file.save(CLIENT_SECRET_PATH)
        return jsonify({"message": "Client secret uploaded successfully."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/start_oauth', methods=['GET'])
def start_oauth():
    """
    Generate an OAuth authorization URL and send it back to the client.
    """
    try:
        if not is_client_secret_uploaded():
            return jsonify({"error": "Client secret not uploaded. Please upload first."}), 400

        flow = get_flow()
        authorization_url, _ = flow.authorization_url(prompt='consent')
        return jsonify({"authorization_url": authorization_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/oauth2callback', methods=['GET'])
def oauth2callback():
    """
    Handle the OAuth callback and retrieve credentials.
    """
    try:
        flow = get_flow()
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials

        # Save the credentials for future use
        with open(TOKEN_PATH, 'w') as token_file:
            token_file.write(creds.to_json())

        return jsonify({'message': 'Authentication successful! You can close this tab/window.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/check_auth', methods=['GET'])
def check_auth():
    """
    Check if we have valid credentials.
    Return JSON: { "authenticated": True/False }
    """
    if os.path.exists(TOKEN_PATH):
        # Attempt to load credentials and verify validity
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        if creds and creds.valid:
            return jsonify({"authenticated": True})

    return jsonify({"authenticated": False})


def get_authenticated_service():
    """Authenticate and return the YouTube API service if credentials exist and are valid."""
    if not os.path.exists(TOKEN_PATH):
        raise Exception("No token found. Please authenticate first.")

    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise Exception("No valid credentials. Please authenticate first.")

    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=creds)


def search_videos(query, max_results=5):
    """Search for YouTube videos using an API key or an authenticated service."""
    # If you prefer to use an API Key, remove the get_authenticated_service usage.
    youtube = get_authenticated_service()
    search_response = youtube.search().list(
        q=query,
        part='id',
        type='video',
        maxResults=max_results
    ).execute()

    video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
    return video_ids if video_ids else None


def get_captions(video_id):
    """Grab captions for a given video ID using authorized credentials."""
    youtube = get_authenticated_service()
    captions_response = youtube.captions().list(
        part='snippet',
        videoId=video_id
    ).execute()

    caption_items = captions_response.get('items', [])
    if not caption_items:
        return None

    # Use the first available caption track
    caption_id = caption_items[0]['id']
    caption_download = youtube.captions().download(
        id=caption_id,
        tfmt='srt'
    ).execute()

    return caption_download.decode('utf-8')


def parse_captions(caption_content):
    """Parse SRT or VTT caption content into plain text."""
    lines = []
    for line in caption_content.splitlines():
        # Skip timestamps and line numbers
        if not line.strip().isdigit() and '-->' not in line:
            lines.append(line.strip())
    return " ".join(lines)


def rag_system(query, transcript):
    """
    Invoke a conversation with ChatGPT using LangChain.
    """
    document = [Document(page_content=transcript)]
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    text_chunks = text_splitter.split_documents(document)

    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        encode_kwargs={'normalize_embeddings': True}
    )

    vectorstore = FAISS.from_documents(text_chunks, embeddings)
    # For demonstration, we skip saving the local vectorstore or use ephemeral storage

    retriever = vectorstore.as_retriever()

    template = """
    You are an expert assistant at writing comprehensive summaries of Youtube video transcripts in less than 300 words.
    Generate a summary discussing the main points of the following transcript.
    Use the provided context only to answer the question(s):

    <context>
    {context}
    </context>

    Question: {input}
    """
    prompt = ChatPromptTemplate.from_template(template)
    doc_chain = create_stuff_documents_chain(llm, prompt)
    chain = create_retrieval_chain(retriever, doc_chain)

    response = chain.invoke({"input": query})
    return response.get("answer", "No Information")


@app.route('/get_transcript', methods=['POST'])
def get_transcript():
    """
    Main endpoint to get the video transcript (by search query) and run RAG summarization.
    """
    try:
        # First, check if we have valid credentials:
        if not os.path.exists(TOKEN_PATH):
            return jsonify({"error": "User not authenticated. Please authenticate first."}), 401

        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        if not creds.valid:
            # Attempt a refresh if possible
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                return jsonify({"error": "Credentials invalid or expired. Please re-authenticate."}), 401

        # Now proceed with the user query
        data = request.get_json()
        query = data.get('query', '').strip()
        if not query:
            return jsonify({"error": "Query is required"}), 400

        video_ids = search_videos(query)
        if not video_ids:
            return jsonify({"error": "No videos found for the query"}), 404

        video_id = video_ids[0]
        captions = get_captions(video_id)
        if not captions:
            return jsonify({'error': f'Captions unavailable for video ID: {video_id}'}), 404

        transcript = parse_captions(captions)
        final_summary = rag_system(query, transcript)

        return jsonify({"transcript": final_summary}), 200

    except Exception as e:
        app.logger.error(f"Error processing request: {str(e)}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # For local testing
    app.run(host="0.0.0.0", port=7000, debug=True)
