from google import genai
from google.genai import types
from math import sqrt

from app.config import Settings


def embed_query(query: str, settings: Settings) -> list[float]:
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.embed_content(
        model=settings.gemini_embedding_model,
        contents=query,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=settings.embedding_dimensions,
        ),
    )
    if not response.embeddings or not response.embeddings[0].values:
        raise RuntimeError("Gemini returned an empty embedding")
    vector = list(response.embeddings[0].values)
    norm = sqrt(sum(value * value for value in vector))
    if not norm:
        raise RuntimeError("Gemini returned a zero vector")
    return [value / norm for value in vector]
