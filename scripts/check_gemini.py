import os
import sys
from dotenv import load_dotenv
from google import genai

load_dotenv()
model = os.environ.get("REBATEIQ_MODEL", "gemini-3.5-flash")
try:
    client = genai.Client()
    resp = client.models.generate_content(
        model=model,
        contents="Reply with exactly: RebateIQ Gemini connection OK",
    )
    print(f"[{model}] ->", resp.text.strip())
except Exception as e:
    sys.exit(f"Gemini error: {e}")
