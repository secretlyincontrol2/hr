import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

response = client.models.generate_content(
    model="gemini-2.5-flash-lite",
    contents="Search for 'Dorahacks hackathon' and tell me the results.",
    config=types.GenerateContentConfig(
        tools=[types.Tool(googleSearch=types.GoogleSearch())],
    )
)

print("TEXT:", response.text)
if response.candidates and response.candidates[0].grounding_metadata:
    chunks = response.candidates[0].grounding_metadata.grounding_chunks
    for chunk in chunks:
        if hasattr(chunk, 'web') and chunk.web:
            print("URL:", chunk.web.uri)
            print("TITLE:", chunk.web.title)
