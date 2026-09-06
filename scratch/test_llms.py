import os
import sys
import json
import urllib.request
import urllib.error

def test_llms():
    print("=== LLM PREFLIGHT VERIFICATION ===")
    
    # 1. Check Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    print(f"Gemini API Key in env: {'FOUND' if gemini_key else 'NOT IN ENV'}")
    
    # 2. Check Groq
    groq_key = os.environ.get("GROQ_API_KEY")
    print(f"Groq API Key in env: {'FOUND' if groq_key else 'NOT IN ENV'}")
    
    # 3. Check OpenRouter
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    print(f"OpenRouter API Key in env: {'FOUND' if openrouter_key else 'NOT IN ENV'}")
    
    # 4. Check OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY")
    print(f"OpenAI API Key in env: {'FOUND' if openai_key else 'NOT IN ENV'}")

if __name__ == "__main__":
    test_llms()
