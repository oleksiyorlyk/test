
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Load backend/.env regardless of the working directory
load_dotenv(Path(__file__).resolve().parent / ".env")

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

response = client.responses.create(
    model=os.getenv("OPENAI_MODEL", "gpt-6-luna"),
    reasoning={"effort": "none"},
    input="Reply with exactly: OpenAI API connection successful.",
    store=False,
)

print(response.output_text)