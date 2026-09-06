import os
import socket
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv('E:/n8n/flight-agent-hackathon/.env')

class Settings:
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    
    DB_HOST: str = os.getenv("DB_HOST", "aws-0-ap-southeast-1.pooler.supabase.com")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_USER: str = os.getenv("DB_USER", "postgres.ewqzxwurcmdgnvoczeyz")
    DB_NAME: str = os.getenv("DB_NAME", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "w+jH*8AT?VjUP@?")

    @property
    def resolved_host(self) -> str:
        try:
            socket.gethostbyname(self.DB_HOST)
            return self.DB_HOST
        except Exception:
            # Fallback IP for aws-0-ap-southeast-1.pooler.supabase.com if transient DNS fails
            return "52.77.146.31"

settings = Settings()
