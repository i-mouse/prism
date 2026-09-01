import os
from openai import AsyncOpenAI,AuthenticationError
from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types
load_dotenv()

class AIService:
    def __init__(self):

        AI_BASE_URL='https://generativelanguage.googleapis.com/v1beta/openai/'
        self.client = AsyncOpenAI(api_key= os.getenv("AI_API_KEY"),base_url= AI_BASE_URL)
        self.genai_client = genai.Client(api_key=os.getenv("AI_API_KEY"))


    async def analyize_text(self,text:str):
        """Send text to the LLM and return the response"""

        try:
            response =await self.client.chat.completions.create(
                model=os.getenv("LLM_SUMMARY_MODEL"),
                messages=[
                    {"role":"system","content" : "You are a helpful Prism analyst."},
                    {"role":"user","content":f"Summarize this prism doc : \n\n{text[:100000]}"}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
         
        except AuthenticationError as ae:
               print(f"AuthenticationError: {ae}")

        except Exception as e:
            print(f"Error: {e}")
            return "Error while analyzing the prism doc"

    async def transcribe_audio(self, file_path: str):
        print(f" [AUDIO] Uploading audio to Gemini: {file_path}...")
        audio_file = await self.genai_client.aio.files.upload(
            file=file_path,
            config=genai_types.UploadFileConfig(mime_type="audio/mp3"),
        )

        print(f" [CLOUD] File uploaded: {audio_file.uri}")

        response = await self.genai_client.aio.models.generate_content(
            model=os.getenv("LLM_SUMMARY_MODEL"),
            contents=[audio_file, "Please transcribe this audio and provide  result in proper format without missing any detail from the audio.Need word-for-word transcription"],
        )

        print(" [OK] Audio processed successfully.")
        return response.text

