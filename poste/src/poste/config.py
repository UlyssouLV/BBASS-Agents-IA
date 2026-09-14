import os

from dotenv import load_dotenv

load_dotenv()

POSTE_HOST = os.environ.get("POSTE_HOST", "127.0.0.1")
POSTE_PORT = int(os.environ.get("POSTE_PORT", "8100"))
VM_CENTRALE_BASE_URL = os.environ.get("VM_CENTRALE_BASE_URL", "http://localhost:8000").rstrip("/")
