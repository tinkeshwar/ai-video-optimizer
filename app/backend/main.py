from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routes import router
import backend.db as db
from contextlib import asynccontextmanager
import logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logging.info("Initializing database...")
        db.init_db()
        yield
    except Exception as e:
        logging.error(f"Error initializing database: {e}")
        raise
    finally:
        logging.info("Shutting down...")

app = FastAPI(
    title="API",
    description="API Description",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware to the FastAPI app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(router)