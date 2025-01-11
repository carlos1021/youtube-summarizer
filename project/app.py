from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import CouldNotRetrieveTranscript
from googleapiclient.discovery import build
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


load_dotenv()


app = Flask(__name__)

CORS(app, origins=[
    'https://summarizer-c3229.firebaseapp.com',
    'https://summarizer-c3229.web.app',
    'http://localhost:7600'
],
methods=["GET", "POST", "OPTIONS"],
allow_headers=["Content-Type"])

MODEL = "gpt-4o-mini"
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
llm = ChatOpenAI(model = MODEL)
API_KEY = os.getenv('API_KEY')
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

def search_videos(query, max_results=5, order='date'):
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
    search_response = youtube.search().list(
        q=query,
        part='id',
        type='video',
        maxResults=max_results
    ).execute()

    video_ids = [item['id']['videoId'] for item in search_response['items']]
    return video_ids if video_ids else None

def youtube_transcript(video_ids):
    print(video_ids)
    for video_id in video_ids:
        try:
            # Attempt to retrieve the transcript for the current video ID
            print(f"Attempting to retrieve transcript for video ID: {video_id}")
            return YouTubeTranscriptApi.get_transcript(video_id)
        except CouldNotRetrieveTranscript as e:
            # Log the error and continue to the next video ID
            print(f"Could not retrieve transcript for video {video_id}: {e}")
            continue
    # If none of the video IDs have a transcript, return None
    print("No transcripts available for any of the provided video IDs.")
    return None


def grab_transcript(raw_transcript):
    return ' '.join([item['text'] for item in raw_transcript])

def rag_system(query, transcript):
    """
    Invoke a conversation with ChatGPT using the Python LangChain implementation.
    Input: query (string) from the user 
    Output: augmented response (string) from LLM
    """
    # Start the RAG system process
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

def chat_with_chatgpt(transcript):
	response = client.chat.completions.create(model=MODEL,
	    messages=[
				{
					"role": "system",
					"content": "You are an expert assistant at writing comprehensive summaries of Youtube video transcripts in less than 250 words."
				}, 
				{
					"role": "user",
					"content": f"Generate a summary which discusses the main points of the following transcript: {transcript}"
				}
			])

	message = response.choices[0].message.content
	return message

@app.route('/get_transcript', methods=['POST'])
def grab_results():
    try:
        data = request.get_json()
        query = data.get('query', '')
        print(query)
        if not query:
            return jsonify({'error': 'Query is required'}), 400

        video_id = search_videos(query)
        if not video_id:
            return jsonify({'error': 'No videos found for the query'}), 404

        transcript = youtube_transcript(video_id)
        if not transcript:
            return jsonify({'error': f'Transcript unavailable for video ID: {video_id}'}), 404

        transcript_text = grab_transcript(transcript)
        print(chat_with_chatgpt(transcript_text))
        return jsonify({'transcript': rag_system(query, transcript_text)})
    except Exception as e:
        app.logger.error(f"Error processing request: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
