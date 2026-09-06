import os
import sys

def inspect_env():
    print("=== ENVIRONMENT KEYS AUDIT ===")
    keys = sorted(os.environ.keys())
    relevant_keywords = ["POSTGRES", "SUPABASE", "DATABASE", "DB", "N8N", "OPENAI", "ANTHROPIC", "GEMINI", "PINECONE", "GMAIL", "EMAIL", "SMTP", "MCP", "API", "KEY", "TOKEN", "URL"]
    
    found = []
    for k in keys:
        upper = k.upper()
        if any(kw in upper for kw in relevant_keywords):
            val = os.environ[k]
            masked = f"SET (length={len(val)})" if val else "EMPTY"
            found.append(f"{k}: {masked}")
    
    if found:
        print("\n".join(found))
    else:
        print("No matching environment keys found.")
    print("==============================")

if __name__ == "__main__":
    inspect_env()
