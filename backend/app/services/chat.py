from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.schemas.chat import ChatMessage


def _create_model(api_key: str, model_name: str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=model_name,
        api_key=api_key,
        max_output_tokens=1024,
    )


def _create_conversation(messages: list[ChatMessage]) -> list[BaseMessage]:
    return [
        HumanMessage(content=message.content)
        if message.role == "user"
        else AIMessage(content=message.content)
        for message in messages
    ]


def generate_reply(
    messages: list[ChatMessage],
    api_key: str,
    model_name: str,
) -> str:
    response = _create_model(api_key, model_name).invoke(
        _create_conversation(messages)
    )
    return str(response.content)


async def stream_reply(
    messages: list[ChatMessage],
    api_key: str,
    model_name: str,
) -> AsyncIterator[str]:
    model = _create_model(api_key, model_name)
    async for chunk in model.astream(_create_conversation(messages)):
        if isinstance(chunk.content, str) and chunk.content:
            yield chunk.content
