import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env (for local dev)
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

from app import app as flask_app

# Vercel expects the app to be named 'app'
app = flask_app
