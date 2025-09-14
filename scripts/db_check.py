from __future__ import annotations
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
url = os.getenv("DATABASE_URL")
print("DATABASE_URL=", url)
if not url:
    raise SystemExit("DATABASE_URL not set")

if url.startswith("postgresql") and "sslmode=" not in url:
    sep = "&" if "?" in url else "?"
    url = f"{url}{sep}sslmode=require"

engine = create_engine(url, pool_pre_ping=True)
with engine.connect() as conn:
    print("connected ok, server version:", conn.exec_driver_sql("select version();").scalar())
