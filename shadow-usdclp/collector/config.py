import os

DATABASE_URL = os.environ["DATABASE_URL"]
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))

CMF_API_KEY = os.getenv("CMF_API_KEY", "")
BUDA_API_KEY = os.getenv("BUDA_API_KEY", "")
BUDA_API_SECRET = os.getenv("BUDA_API_SECRET", "")
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "")
