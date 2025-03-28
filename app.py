from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import json
import os
import time
import uuid
import asyncio
from typing import Dict, List, Optional
import azure.cognitiveservices.speech as speechsdk
from azure.core.credentials import AzureKeyCredential
from azure.ai.translation.text import TextTranslationClient
from azure.ai.translation.text.models import InputTextItem
import uuid
import time
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI
from dotenv import load_dotenv
load_dotenv()


app = FastAPI(title="Cold Calling AI Assistant")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration from environment variables
SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "eastus")
TRANSLATOR_KEY = os.getenv("AZURE_TRANSLATOR_KEY")
TRANSLATOR_REGION = os.getenv("AZURE_TRANSLATOR_REGION", "global")
OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER", "cold-calling-data")
INITIAL_DATA_BLOB = os.getenv("INITIAL_DATA_BLOB", "initial_data.json")

# Initialize Azure clients
speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
translator_credential = AzureKeyCredential(TRANSLATOR_KEY)
translator_client = TextTranslationClient(credential=translator_credential)
# Modify the OpenAI client initialization
try:
    openai_client = AzureOpenAI(
        api_key=OPENAI_API_KEY,
        azure_endpoint=OPENAI_ENDPOINT,
        api_version="2023-05-15"
    )
    
    # Verify deployment exists (optional additional check)
    try:
        openai_client.chat.completions.create(
            model=OPENAI_DEPLOYMENT,
            messages=[{"role": "system", "content": "Test deployment"}],
            max_tokens=10
        )
    except Exception as deployment_error:
        print(f"Deployment verification failed: {deployment_error}")
        raise
except Exception as init_error:
    print(f"OpenAI client initialization error: {init_error}")
    # Optionally, you could fall back to a mock response generation
    async def generate_ai_response(session_id: str, transcript: str) -> str:
        return "I'm currently experiencing some technical difficulties. Could you please rephrase your question?"

# In-memory store for active websocket connections and conversation history
active_connections: Dict[str, WebSocket] = {}
conversation_history: Dict[str, List[Dict]] = {}
feedback_data: List[Dict] = []

# Load initial data from Azure Blob Storage
def load_initial_data():
    try:
        blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(STORAGE_CONTAINER)
        blob_client = container_client.get_blob_client(INITIAL_DATA_BLOB)
        
        data = blob_client.download_blob().readall()
        return json.loads(data)
    except Exception as e:
        print(f"Error loading initial data: {str(e)}")
        # Fallback to local file if blob storage fails
        try:
            with open("initial_data.json", "r") as f:
                return json.load(f)
        except:
            # Return minimal default data if all loading fails
            return {
                "sales_scripts": [
                    {"name": "Introduction", "text": "Hello, my name is [Name] from [Company]. How are you today?"}
                ],
                "faqs": [
                    {"question": "What products do you offer?", "answer": "We offer a range of solutions. Could you tell me more about your specific needs?"}
                ],
                "product_details": [
                    {"name": "Default Product", "description": "Our flagship product designed to meet your needs."}
                ]
            }

# Initial data as a global variable
INITIAL_DATA = load_initial_data()

# Format the system prompt with initial data
def get_system_prompt():
    return f"""

Example GOOD responses:
"Could you help me understand your current setup better?"
"Let me check if we have inventory in your preferred size."
"Would next Tuesday work for a quick demo?"

BAD responses:
"Suggest asking about their current setup"
"Try saying: Let me check inventory"

Focus on:
- Direct quotes only
- Natural conversation flow
- No suggestion prefixes
"""


async def translate_text(
    text: str,
    target_language: str = "en",
    translator_client: TextTranslationClient = None
) -> str:
    """
    Translate text to target language.
    """
    if not text or not isinstance(text, str):
        return text

    if translator_client is None:
        translator_client = TextTranslationClient(credential=translator_credential)

    try:
        # Use the correct translation method
        translation_result = translator_client.translate(
    body=[InputTextItem(text=text)],  # Correct method
    to=[target_language]
)


        # Return translated text
        return translation_result[0].translations[0].text
    except Exception as e:
        print(f"Translation error: {str(e)}")
        return text  # Return original if translation fails
    

# Generate AI response
async def generate_ai_response(session_id: str, transcript: str) -> str:
    try:
        # Get conversation history for context
        history = conversation_history.get(session_id, [])
        
        # Create message list for AI
        messages = [
            {"role": "system", "content": get_system_prompt()},
        ]
        
        # Add history context
        for entry in history[-10:]:  # Keep last 10 exchanges for context
            messages.append({"role": "user", "content": entry.get("transcript", "")})
            if entry.get("response"):
                messages.append({"role": "assistant", "content": entry.get("response", "")})
        
        # Add current transcript
        messages.append({"role": "user", "content": f"Customer said: {transcript}"})
        
        # Generate AI response
        response = openai_client.chat.completions.create(
            model=OPENAI_DEPLOYMENT,
            messages=messages,
            temperature=0.7,
            max_tokens=150
        )
        
        # Extract and clean response
        response_text = response.choices[0].message.content
        
        # Remove suggestion prefixes and keep only the response
        if "Suggest the sales representative to respond:" in response_text:
            # Extract text between quotes if present
            if '"' in response_text:
                response_text = response_text.split('"', 1)[-1].rsplit('"', 1)[0]
            else:
                # Fallback: remove the entire prefix
                response_text = response_text.split(":", 1)[-1].strip()
        elif "respond:" in response_text:
            # Handle responses without quotes
            response_text = response_text.split("respond:", 1)[-1].strip()

        # In your history appending:
        conversation_history.setdefault(session_id, []).append({
            "timestamp": time.time(),
            "transcript": transcript,
            "response": response_text  # Store the CLEANED response
})
        
        return response_text
        
    except Exception as e:
        print(f"AI response generation error: {str(e)}")
        # Fallback response that maintains conversation flow
        return "Could you clarify your specific requirements? This will help me provide the best solution."
    

# Store feedback
async def store_feedback(background_tasks: BackgroundTasks, session_id: str, response_id: str, is_helpful: bool):
    feedback_data.append({
        "session_id": session_id,
        "response_id": response_id,
        "is_helpful": is_helpful,
        "timestamp": time.time()
    })
    
    # In a production environment, you would save this to persistent storage
    # Here, we'll just print it for demonstration
    print(f"Feedback received: Session {session_id}, Response {response_id}, Helpful: {is_helpful}")

# WebSocket endpoint for real-time communication
# WebSocket endpoint for real-time communication
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    active_connections[session_id] = websocket

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "audio":
                transcript = data.get("transcript", "")
                try:
                    # Attempt to detect and translate if needed
                    detect_result = translator_client.translate_text(texts=[transcript])
                    source_language = detect_result[0].language

                    if source_language != "en":
                        translated_transcript = await translate_text(
                            transcript,
                            target_language="en",
                            translator_client=translator_client
                        )
                    else:
                        translated_transcript = transcript

                    # Generate AI response
                    response = await generate_ai_response(session_id, translated_transcript)

                    # Translate response back if needed
                    if source_language != "en":
                        response = await translate_text(
                            response,
                            target_language=source_language,
                            translator_client=translator_client
                        )

                    # Generate a unique ID for this response for feedback tracking
                    response_id = str(uuid.uuid4())

                    # Send response back to client
                    await websocket.send_json({
                        "type": "guidance",
                        "response_id": response_id,
                        "text": response
                    })
                except Exception as translation_error:
                    print(f"Translation process error: {translation_error}")
                    # Fallback to sending untranslated response
                    response = await generate_ai_response(session_id, transcript)
                    await websocket.send_json({
                        "type": "guidance",
                        "response_id": str(uuid.uuid4()),
                        "text": response
                    })
            elif data.get("type") == "feedback":

                # Process feedback
                response_id = data.get("response_id")
                is_helpful = data.get("is_helpful", False)
                
                # Store feedback
                feedback_data.append({
                    "session_id": session_id,
                    "response_id": response_id,
                    "is_helpful": is_helpful,
                    "timestamp": time.time()
                })
                
                await websocket.send_json({
                    "type": "confirmation",
                    "message": "Feedback received"
                })

    except Exception as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        # Clean up when connection closes
        if session_id in active_connections:
            del active_connections[session_id]

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)