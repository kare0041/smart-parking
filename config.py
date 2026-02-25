import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    DATABASE_URL = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:password@localhost:5432/smart_parking",
    )
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")

    # Individual DB params (preferred when the password contains special chars)
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "5432")
    DB_NAME = os.environ.get("DB_NAME", "smart_parking")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "password")

    # MTN Mobile Money
    MTN_MOMO_BASE_URL = os.environ.get("MTN_MOMO_BASE_URL", "https://sandbox.momodeveloper.mtn.com")
    MTN_MOMO_SUBSCRIPTION_KEY = os.environ.get("MTN_MOMO_SUBSCRIPTION_KEY", "")
    MTN_MOMO_API_USER = os.environ.get("MTN_MOMO_API_USER", "")
    MTN_MOMO_API_KEY = os.environ.get("MTN_MOMO_API_KEY", "")
    MTN_MOMO_TARGET_ENVIRONMENT = os.environ.get("MTN_MOMO_TARGET_ENVIRONMENT", "sandbox")
    MTN_MOMO_CURRENCY = os.environ.get("MTN_MOMO_CURRENCY", "RWF")
    GRACE_PERIOD_MINUTES = int(os.environ.get("GRACE_PERIOD_MINUTES", "15"))

    # Africa's Talking SMS
    AFRICASTALKING_API_KEY = os.environ.get("AFRICASTALKING_API_KEY", "")
    AFRICASTALKING_USERNAME = os.environ.get("AFRICASTALKING_USERNAME", "sandbox")
