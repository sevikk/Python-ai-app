"""Translate chat inputs to LangChain messages and call the Gemini model."""

from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.schemas.chat import ChatMessage
from app.schemas.tasks import TaskExtractionResponse


def _create_model(api_key: str, model_name: str) -> ChatGoogleGenerativeAI:
    """Create a configured Gemini chat model for one provider operation."""
    return ChatGoogleGenerativeAI(
        model=model_name,
        api_key=api_key,
        max_output_tokens=1024,
    )


def _create_conversation(messages: list[ChatMessage]) -> list[BaseMessage]:
    """Map validated API messages to LangChain user and assistant messages."""
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
    """Invoke Gemini once and return the assistant's complete text response."""
    response = _create_model(api_key, model_name).invoke(
        _create_conversation(messages)
    )
    return str(response.content)


async def stream_reply(
    messages: list[ChatMessage],
    api_key: str,
    model_name: str,
) -> AsyncIterator[str]:
    """Yield nonempty text chunks and close the provider stream on cancellation."""
    stream = _create_model(api_key, model_name).astream(
        _create_conversation(messages)
    )
    try:
        async for chunk in stream:
            if isinstance(chunk.content, str) and chunk.content:
                yield chunk.content
    finally:
        if hasattr(stream, "aclose"):
            await stream.aclose()


def extract_tasks(
    text: str,
    api_key: str,
    model_name: str,
) -> TaskExtractionResponse:
    """Ask Gemini for schema-constrained tasks and validate the resulting data."""
    structured_model = _create_model(api_key, model_name).with_structured_output(
        TaskExtractionResponse,
        method="function_calling",
    )
    result = structured_model.invoke(
        [
            (
                "system",
                "Extract only actionable tasks explicitly stated in the input. "
                "Do not invent tasks or deadlines. Use an ISO date for a due "
                "date only when it is explicit; otherwise use null. Use "
                "medium priority when the text does not clearly indicate "
                "urgency. Return an empty task list when no tasks are present.",
            ),
            ("human", text),
        ]
    )
    return TaskExtractionResponse.model_validate(result)
