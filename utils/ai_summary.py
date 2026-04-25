import os
from dotenv import load_dotenv
from google import genai

# Load .env
load_dotenv()

# Get API key
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def test_gemini():
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Give me a one sentence summary of retail sales trends."
        )

        return {
            "status": "success",
            "text": response.text
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


# Test run
print(test_gemini())