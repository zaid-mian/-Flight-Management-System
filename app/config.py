import os
import socket
from dotenv import load_dotenv

# Dynamically locate project root .env file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

class Settings:
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    
    DB_HOST: str = os.getenv("POSTGRES_HOST") or os.getenv("DB_HOST", "aws-0-ap-southeast-1.pooler.supabase.com")
    DB_PORT: int = int(os.getenv("POSTGRES_PORT") or os.getenv("DB_PORT", "5432"))
    DB_USER: str = os.getenv("POSTGRES_USER") or os.getenv("DB_USER", "postgres.ewqzxwurcmdgnvoczeyz")
    DB_NAME: str = os.getenv("POSTGRES_DB") or os.getenv("DB_NAME", "postgres")
    DB_PASSWORD: str = os.getenv("POSTGRES_PASSWORD") or os.getenv("DB_PASSWORD", "w+jH*8AT?VjUP@?")


    @property
    def resolved_host(self) -> str:
        try:
            socket.gethostbyname(self.DB_HOST)
            return self.DB_HOST
        except Exception:
            # Fallback IP for aws-0-ap-southeast-1.pooler.supabase.com if transient DNS fails
            return "52.77.146.31"

settings = Settings()
