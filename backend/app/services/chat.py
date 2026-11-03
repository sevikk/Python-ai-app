from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage

from app.schemas.chat import ChatMessage


def generate_reply(
    messages: list[ChatMessage],
    api_key: str,
    model_name: str,
) -> str:
    model = ChatGoogleGenerativeAI(
        model=model_name,
        api_key=api_key,
        max_output_tokens=1024,
    )
    conversation = [
        HumanMessage(content=message.content)
        if message.role == "user"
        else AIMessage(content=message.content)
        for message in messages
    ]
    response = model.invoke(conversation)
    return str(response.content)
