import os
import requests

from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    os.environ[k.strip()] = v.strip()

api_key = os.getenv("GROQ_API_KEY")
print("Key starts with:", api_key[:10] if api_key else None)
url = "https://api.groq.com/openai/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}
payload = {
    "model": "llama-3.3-70b-versatile",
    "messages": [{"role": "user", "content": "Hola " * 5000}],  # ~5000 words
    "temperature": 0.1,
}
r = requests.post(url, headers=headers, json=payload)
print(r.status_code)
print(r.text)
