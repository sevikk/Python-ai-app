from langchain_google_genai import ChatGoogleGenerativeAI


def generate_reply(message: str, api_key: str, model_name: str) -> str:
    model = ChatGoogleGenerativeAI(
        model=model_name,
        api_key=api_key,
        max_output_tokens=1024,
    )
    response = model.invoke(message)
    return str(response.content)
