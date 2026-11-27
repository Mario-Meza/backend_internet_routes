# tests/conftest.py
import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-ci-only-32-bytes-long")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGO_DB_NAME", "rutas_digitales_test")
os.environ.setdefault("CLOUDINARY_CLOUD_NAME", "test-cloud")
os.environ.setdefault("CLOUDINARY_API_KEY", "test-key")
os.environ.setdefault("CLOUDINARY_API_SECRET", "test-secret")