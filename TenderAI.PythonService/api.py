from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage
from agent_service import app as agent_app
from pydantic import BaseModel

app = FastAPI(title="TenderAI python agent")

class QueryRequest(BaseModel):
    question : str
    thread_id : str = "default thread Id"

@app.post("/ask")
async def ask_agent(request :QueryRequest):
    """API endpoint to ask agent questions"""
    try:
        input_config = { "configurable" :{ "thread_id" : request.thread_id} }
        input_message = {"messages" :[HumanMessage(content=request.question)] }

        result = await agent_app.ainvoke(input=input_message,config=input_config) 
        final_raw_answer = result["messages"][-1].content

        if isinstance(result,list):
            final_answer = final_raw_answer[0].get("text", str(final_raw_answer))
        else:
            final_answer  = final_raw_answer

        return {"answer": final_answer}
    
    except Exception as e:
        print(f"Error while processing ask agent API : {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app,host= "0.0.0.0",port= 8000)    