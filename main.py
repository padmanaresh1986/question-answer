from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import openai  # or your preferred LLM library
import json
from dotenv import load_dotenv
import os
from openai import OpenAI
from fastapi import Body



# Load environment variables from .env
load_dotenv()

# Get AI Together API key from environment variable
ait_api_key = os.getenv("AIT_API_KEY")

# Initialize the client at the top of your file (after imports)
client = OpenAI(
    api_key=ait_api_key,
    base_url="https://api.together.xyz/v1"
)

app = FastAPI()

# Store conversation state (in-memory for simplicity, use DB in production)
conversations = {}

json_schema = '''
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Personal Details",
  "type": "object",
  "required": ["firstName", "lastName", "email", "age"],
  "properties": {
    "firstName": {
      "type": "string",
      "description": "The person's first name"
    },
    "lastName": {
      "type": "string",
      "description": "The person's last name"
    },
    "email": {
      "type": "string",
      "format": "email",
      "description": "The person's email address"
    },
    "age": {
      "type": "string",
      "minimum": 18,
      "description": "The person's age (must be 18+)"
    },
    "phone": {
      "type": "string",
      "description": "Phone number (optional)"
    },
    "address": {
      "type": "object",
      "properties": {
        "street": {
          "type": "string",
          "description": "Street address"
        },
        "city": {
          "type": "string",
          "description": "City"
        },
        "country": {
          "type": "string",
          "enum": ["USA", "Canada", "UK", "Australia", "India", "Others"],
          "description": "Country of residence"
        }
      }
    }
  }
}
'''


@app.get("/start_conversation")
async def start_conversation():
    conversation_id = str(len(conversations) + 1)

    # Initial system prompt
    system_prompt = f"""
    You are a JSON form filling assistant. Your task is to:
    1. Analyze this JSON schema: {json_schema}
    2. Determine what information is needed to complete it
    3. Ask one clear question at a time to gather each required field
    4. Never ask for more than one piece of information at once
    5. Confirm when all required fields are collected
    6. Finally return the completed JSON

    Current rules:
    - Only ask about fields that are required in the schema
    - If a field has enum values, present them as options
    - For nested objects, ask questions progressively
    - Maintain context throughout the conversation
    """

    conversations[conversation_id] = {
        "schema": json_schema,
        "messages": [{"role": "system", "content": system_prompt}],
        "collected_data": {}
    }

    # Then modify your API call to:
    response = client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        messages=conversations[conversation_id]["messages"]
    )

    first_question = response.choices[0].message.content
    conversations[conversation_id]["messages"].append(
        {"role": "assistant", "content": first_question}
    )

    return {"conversation_id": conversation_id, "question": first_question}


@app.post("/submit_answer")
async def submit_answer(conversation_id: str = Body(...),  answer: str = Body(...)):
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Add user's answer to conversation history
    conversations[conversation_id]["messages"].append(
        {"role": "user", "content": answer}
    )

    # Then modify your API call to:
    response = client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        messages=conversations[conversation_id]["messages"]
    )

    assistant_response = response.choices[0].message.content

    # Check if response is the completed JSON
    if assistant_response.startswith("{") and assistant_response.endswith("}"):
        try:
            completed_json = json.loads(assistant_response)
            return {"status": "complete", "json": completed_json}
        except:
            pass

    # If not complete, continue conversation
    conversations[conversation_id]["messages"].append(
        {"role": "assistant", "content": assistant_response}
    )

    return {"status": "in_progress", "question": assistant_response}