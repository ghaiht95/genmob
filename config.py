import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """
    Flask application configuration.
    """
    # Secret key for sessions and forms
    SECRET_KEY = os.getenv('SECRET_KEY', 'mysecretkey')

    # Database configuration
    DB_PATH = os.getenv('DATABASE_PATH', '/app/dbdata/app.db')
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}?timeout=30&check_same_thread=False"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # SQLite optimizations
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # Mail configuration
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@example.com')

    # SoftEther VPN configuration
    SOFTETHER_SERVER_IP = os.getenv('SOFTETHER_SERVER_IP')
    SOFTETHER_SERVER_PORT = int(os.getenv('SOFTETHER_SERVER_PORT', '5555'))
    SOFTETHER_ADMIN_PASSWORD = os.getenv('SOFTETHER_ADMIN_PASSWORD')
    VPNCMD_PATH = os.getenv('VPNCMD_PATH', '/usr/local/vpnserver/vpncmd')
    
    if not SOFTETHER_SERVER_IP:
        raise ValueError("SOFTETHER_SERVER_IP must be set in the environment (e.g., docker-compose.yml)")
    if not SOFTETHER_ADMIN_PASSWORD:
        raise ValueError("SOFTETHER_ADMIN_PASSWORD must be set in the .env file or environment")
    
    if not os.path.exists(VPNCMD_PATH):
        raise ValueError(f"vpncmd not found at {VPNCMD_PATH}. Please set VPNCMD_PATH in environment variables.")

    # CORS settings
    CORS_HEADERS = 'Content-Type'

    # Other application settings
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 'yes')