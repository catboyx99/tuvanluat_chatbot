import os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv("GEMINI_API_KEY")
print(f"API Key loaded: {key[:10]}..." if key else "NO API KEY FOUND")

# Test with google.generativeai to list models
import google.generativeai as genai
genai.configure(api_key=key)

print("\n--- Available Embedding Models ---")
for m in genai.list_models():
    if "embed" in m.name.lower():
        print(f"  {m.name} -> {m.display_name}")

print("\n--- Available GenerateContent Models ---")
for m in genai.list_models():
    if "generateContent" in [method.name for method in m.supported_generation_methods]:
        print(f"  {m.name} -> {m.display_name}")
