import os
from openai import AsyncOpenAI,AuthenticationError
from dotenv import load_dotenv

load_dotenv()

class AIService:
    def __init__(self):

        self.client = AsyncOpenAI(api_key= os.getenv("AI_API_KEY"),base_url= os.getenv("AI_BASE_URL"))

    async def analyize_text(self,text:str):
        """Send text to the LLM and return the response"""

        try:
            response =await self.client.chat.completions.create(
                model="gemini-2.5-flash",
                messages=[
                    {"role":"system","content" : "You are a helpful Tender analyst."},
                    {"role":"user","content":"Summarize this tender doc : \n\n{text[:2000]}"}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
         
        except AuthenticationError as ae:
               print(f"AuthenticationError: {ae}")

        except Exception as e:
            print(f"Error: {e}")
            return "Error while analyzing the tender doc"
       
        
if __name__=="__main__":
    import asyncio
    service = AIService()

    result = asyncio.run(service.analyize_text("This is a sample RFP for a construction project."))
    print(result)