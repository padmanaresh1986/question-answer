import chainlit as cl
import httpx
from typing import Dict, Optional

# Your FastAPI server URL
API_BASE_URL = "http://localhost:8000"


class ConversationState:
    def __init__(self):
        self.conversation_id: Optional[str] = None
        self.current_question: Optional[str] = None
        self.completed: bool = False
        self.final_json: Optional[Dict] = None


@cl.on_chat_start
async def start_chat():
    # Initialize a new conversation with the API
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/start_conversation")

    if response.status_code != 200:
        await cl.Message(content="Failed to start conversation").send()
        return

    data = response.json()
    state = ConversationState()
    state.conversation_id = data["conversation_id"]
    state.current_question = data["question"]
    cl.user_session.set("state", state)

    # Send the first question
    await cl.Message(content=state.current_question).send()


@cl.on_message
async def handle_message(message: cl.Message):
    state: ConversationState = cl.user_session.get("state")

    if state.completed:
        await cl.Message(content="The form is already completed. Start a new chat to begin again.").send()
        return

    # Send the answer to the API
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/submit_answer",
            json={
                "conversation_id": state.conversation_id,
                "answer": message.content
            }
        )

    if response.status_code != 200:
        await cl.Message(content="Error processing your answer").send()
        return

    data = response.json()

    if data["status"] == "complete":
        state.completed = True
        state.final_json = data["json"]

        # Display the completed JSON in a nice format
        json_str = "\n".join([f"{k}: {v}" for k, v in state.final_json.items()])
        await cl.Message(
            content=f"Form completed!\n\nHere are your details:\n{json_str}"
        ).send()

        # Show the raw JSON in an expandable section
        await cl.Message(
            content=f"```json\n{state.final_json}\n```",
            language="json"
        ).send()
    else:
        state.current_question = data["question"]
        await cl.Message(content=state.current_question).send()