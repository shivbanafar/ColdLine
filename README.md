# ColdLine

ColdLine is a speech-to-text and translation web application that leverages Azure AI services to provide real-time transcription, translation, and AI-powered insights. The platform is built using Flask, JavaScript, and Tailwind CSS, integrating APIs for speech recognition, language translation, and AI-generated responses.

## Features
- **Speech-to-Text**: Converts spoken words into text using Azure Speech Services.
- **Language Translation**: Supports multiple languages via Azure Translator.
- **AI Guidance**: Generates AI-powered insights based on user inputs.
- **File Uploads**: Allows users to upload audio files for transcription.
- **Real-time Updates**: Displays live transcripts and AI responses.

## Tech Stack
- **Backend**: Flask (Python)
- **Frontend**: HTML, Tailwind CSS, JavaScript
- **APIs Used**:
  - Azure Speech Services
  - Azure Translator
  - Azure OpenAI
  - Azure Storage
- **Deployment**: Uvicorn (ASGI server)

## Setup Instructions

### 1. Clone the Repository
```sh
git clone https://github.com/yourusername/coldline.git
cd coldline
```

### 2. Install Dependencies
```sh
pip install -r requirements.txt
pip install python-dotenv
pip install --upgrade openai httpx
pip install "uvicorn[standard]" websockets wsproto
pip install azure-ai-translation-text
pip install --upgrade azure-ai-translation-text
pip install azure-core azure-ai-translation-text
```

### 3. Configure Environment Variables
Create a `.env` file in the project root and add the following keys:
```env
AZURE_SPEECH_KEY=your_speech_key
AZURE_SPEECH_REGION=your_speech_region
AZURE_TRANSLATOR_KEY=your_translator_key
AZURE_TRANSLATOR_REGION=your_translator_region
AZURE_OPENAI_API_KEY=your_openai_key
AZURE_OPENAI_ENDPOINT=your_openai_endpoint
AZURE_OPENAI_DEPLOYMENT=your_openai_deployment
AZURE_STORAGE_CONNECTION_STRING=your_storage_connection_string
AZURE_STORAGE_CONTAINER=your_storage_container
INITIAL_DATA_BLOB=initial_data.json
```

### 4. Run the Application
```sh
uvicorn app:app --reload
```
The application will start on `http://127.0.0.1:8000/`.

## File Structure
```
ColdLine/
│── static/
│   ├── css/
│   │   ├── styles.css
│   ├── images/
│   │   ├── img1.jpg
│   ├── js/
│   │   ├── app.js
│   ├── index.html
│── app.py
│── requirements.txt
│── .env (not included in repo, must be created)
│── initial_data.json
```
## Project Demo

## 1. Home Menu

This is the entry point for users to interact with the ColdLine Assistant and explore its features.

![Image](https://github.com/user-attachments/assets/3e853541-bd20-4704-970b-466575b622ba)





