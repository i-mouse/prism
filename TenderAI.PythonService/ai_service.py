import os
from openai import AsyncOpenAI,AuthenticationError
from dotenv import load_dotenv
import asyncio
import google.generativeai as genai # <--- New Import
load_dotenv()

class AIService:
    def __init__(self):

        AI_BASE_URL='https://generativelanguage.googleapis.com/v1beta/openai/'
        self.client = AsyncOpenAI(api_key= os.getenv("AI_API_KEY"),base_url= AI_BASE_URL)
        genai.configure(api_key=os.getenv("AI_API_KEY"))
        print("Available Models:")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f" - {m.name}")


    async def analyize_text(self,text:str):
        """Send text to the LLM and return the response"""

        try:
            response =await self.client.chat.completions.create(
                model="gemini-2.5-flash",
                messages=[
                    {"role":"system","content" : "You are a helpful Tender analyst."},
                    {"role":"user","content":f"Summarize this tender doc : \n\n{text[:2000]}"}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
         
        except AuthenticationError as ae:
               print(f"AuthenticationError: {ae}")

        except Exception as e:
            print(f"Error: {e}")
            return "Error while analyzing the tender doc"

    async def transcribe_audio(self, file_path: str):
        print(f" [👂] Uploading audio to Gemini: {file_path}...")
        
        # 1. Upload the file to Google's server
        # We run this in a thread because file upload is blocking
        audio_file = await asyncio.to_thread(
            genai.upload_file, 
            path=file_path,
            mime_type="audio/mp3" 
        )
        
        print(f" [☁️] File uploaded: {audio_file.uri}")

        # 2. Ask Gemini to listen and summarize
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        # We use generate_content_async for non-blocking AI
        response = await model.generate_content_async(
            [audio_file, "Please transcribe this audio and provide  result in proper format without missing any detail from the audio.Need word-for-word transcription"]
        )
        
        print(" [✅] Audio processed successfully.")
        return response.text

           
        
# if __name__=="__main__":
#     import asyncio
#     service = AIService()

#     result = asyncio.run(service.analyize_text("This is a sample RFP for a construction project."))
#     print(result)