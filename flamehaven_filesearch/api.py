"""
FastAPI server for FLAMEHAVEN FileSearch

Production-ready API with file upload, search, and management endpoints.
"""

import logging
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import Config
from .core import FlamehavenFileSearch

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize app
app = FastAPI(
    title="FLAMEHAVEN FileSearch API",
    description="Open source semantic document search powered by Google Gemini",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global searcher instance
searcher: Optional[FlamehavenFileSearch] = None


# Pydantic models
class SearchRequest(BaseModel):
    """Search request model"""

    query: str = Field(..., description="Search query", min_length=1)
    store_name: str = Field(default="default", description="Store name to search in")
    model: Optional[str] = Field(None, description="Model to use for generation")
    max_tokens: Optional[int] = Field(None, description="Maximum output tokens")
    temperature: Optional[float] = Field(None, description="Model temperature")


class SearchResponse(BaseModel):
    """Search response model"""

    status: str
    answer: Optional[str] = None
    sources: Optional[List[dict]] = None
    model: Optional[str] = None
    query: Optional[str] = None
    store: Optional[str] = None
    message: Optional[str] = None


class UploadResponse(BaseModel):
    """Upload response model"""

    status: str
    store: Optional[str] = None
    file: Optional[str] = None
    size_mb: Optional[float] = None
    message: Optional[str] = None


class StoreRequest(BaseModel):
    """Store creation request"""

    name: str = Field(default="default", description="Store name")


class HealthResponse(BaseModel):
    """Health check response"""

    status: str
    version: str
    uptime: float


class MetricsResponse(BaseModel):
    """Metrics response"""

    stores_count: int
    stores: List[str]
    config: dict


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize the searcher on startup"""
    global searcher
    try:
        config = Config.from_env()
        searcher = FlamehavenFileSearch(config=config)
        logger.info("FLAMEHAVEN FileSearch initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize FLAMEHAVEN FileSearch: %s", e)
        raise


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down FLAMEHAVEN FileSearch API")


# Health check
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint

    Returns service status and version
    """
    return {
        "status": "healthy" if searcher else "unhealthy",
        "version": "1.0.0",
        "uptime": time.time(),
    }


# Upload endpoints
@app.post("/upload", response_model=UploadResponse, tags=["Files"])
async def upload_file(
    file: UploadFile = File(..., description="File to upload"),
    store: str = Form(default="default", description="Store name"),
):
    """
    Upload a single file to a store

    Supports: PDF, DOCX, MD, TXT (max 50MB in Lite tier)

    Args:
        file: File to upload
        store: Store name (creates if doesn't exist)

    Returns:
        Upload result with status and file info
    """
    if not searcher:
        raise HTTPException(status_code=503, detail="Service not initialized")

    # Create temporary file
    temp_dir = tempfile.mkdtemp()
    try:
        file_path = os.path.join(temp_dir, file.filename)

        # Save uploaded file
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        logger.info("Uploaded file to temp: %s", file_path)

        # Upload to searcher
        result = searcher.upload_file(file_path, store_name=store)

        return result

    except Exception as e:
        logger.error("Upload failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup temp file
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning("Failed to cleanup temp dir: %s", e)


@app.post("/upload-multiple", tags=["Files"])
async def upload_multiple_files(
    files: List[UploadFile] = File(..., description="Files to upload"),
    store: str = Form(default="default", description="Store name"),
):
    """
    Upload multiple files to a store

    Args:
        files: List of files to upload
        store: Store name (creates if doesn't exist)

    Returns:
        Upload results for all files
    """
    if not searcher:
        raise HTTPException(status_code=503, detail="Service not initialized")

    temp_dir = tempfile.mkdtemp()
    file_paths = []

    try:
        # Save all files
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            file_paths.append(file_path)

        logger.info("Uploaded %d files to temp", len(file_paths))

        # Upload all files
        result = searcher.upload_files(file_paths, store_name=store)

        return result

    except Exception as e:
        logger.error("Multiple upload failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning("Failed to cleanup temp dir: %s", e)


# Search endpoints
@app.post("/search", response_model=SearchResponse, tags=["Search"])
async def search(request: SearchRequest):
    """
    Search files and get AI-generated answers

    Args:
        request: Search request with query and parameters

    Returns:
        Answer with citations from uploaded files
    """
    if not searcher:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        result = searcher.search(
            query=request.query,
            store_name=request.store_name,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Search failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search", response_model=SearchResponse, tags=["Search"])
async def search_get(
    q: str = Query(..., description="Search query", min_length=1),
    store: str = Query(default="default", description="Store name"),
    model: Optional[str] = Query(None, description="Model to use"),
):
    """
    Search files (GET method for simple queries)

    Args:
        q: Search query
        store: Store name
        model: Optional model override

    Returns:
        Answer with citations
    """
    request = SearchRequest(query=q, store_name=store, model=model)
    return await search(request)


# Store management endpoints
@app.post("/stores", tags=["Stores"])
async def create_store(request: StoreRequest):
    """
    Create a new file search store

    Args:
        request: Store creation request

    Returns:
        Store resource name
    """
    if not searcher:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        store_name = searcher.create_store(name=request.name)
        return {"status": "success", "store_name": request.name, "resource": store_name}
    except Exception as e:
        logger.error("Store creation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stores", tags=["Stores"])
async def list_stores():
    """
    List all created stores

    Returns:
        Dictionary of store names to resource names
    """
    if not searcher:
        raise HTTPException(status_code=503, detail="Service not initialized")

    stores = searcher.list_stores()
    return {"status": "success", "count": len(stores), "stores": stores}


@app.delete("/stores/{store_name}", tags=["Stores"])
async def delete_store(store_name: str):
    """
    Delete a store

    Args:
        store_name: Name of store to delete

    Returns:
        Deletion result
    """
    if not searcher:
        raise HTTPException(status_code=503, detail="Service not initialized")

    result = searcher.delete_store(store_name)
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result["message"])

    return result


# Metrics endpoint
@app.get("/metrics", response_model=MetricsResponse, tags=["Monitoring"])
async def get_metrics():
    """
    Get service metrics

    Returns:
        Current metrics and configuration
    """
    if not searcher:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return searcher.get_metrics()


# Root endpoint
@app.get("/", tags=["Info"])
async def root():
    """
    API information endpoint

    Returns:
        API information and available endpoints
    """
    return {
        "name": "FLAMEHAVEN FileSearch API",
        "version": "1.0.0",
        "description": "Open source semantic document search powered by Google Gemini",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "upload": "POST /upload",
            "search": "POST /search or GET /search?q=...",
            "stores": "GET /stores",
        },
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code, content={"status": "error", "message": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error"},
    )


# CLI entry point
def main():
    """Main entry point for CLI"""
    import sys

    import uvicorn

    # Parse simple arguments
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    workers = int(os.getenv("WORKERS", "1"))
    reload = os.getenv("RELOAD", "false").lower() == "true"

    # Check for --help
    if "--help" in sys.argv or "-h" in sys.argv:
        print("FLAMEHAVEN FileSearch API Server")
        print("\nUsage: flamehaven-api [options]")
        print("\nOptions via environment variables:")
        print("  HOST=0.0.0.0        - Server host")
        print("  PORT=8000           - Server port")
        print("  WORKERS=4           - Number of workers (production)")
        print("  RELOAD=true         - Enable auto-reload (development)")
        print("  GEMINI_API_KEY=...  - Google Gemini API key (required)")
        print("\nExample:")
        print("  export GEMINI_API_KEY='your-key'")
        print("  flamehaven-api")
        print("\nDocs: http://localhost:8000/docs")
        return

    # Validate API key
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
        print("Error: GEMINI_API_KEY or GOOGLE_API_KEY must be set")
        print("Example: export GEMINI_API_KEY='your-api-key'")
        sys.exit(1)

    print(f"Starting FLAMEHAVEN FileSearch API on {host}:{port}")
    print(f"Workers: {workers}, Reload: {reload}")
    print(f"Docs: http://{host}:{port}/docs")

    uvicorn.run(
        "flamehaven_filesearch.api:app",
        host=host,
        port=port,
        workers=workers if not reload else 1,
        reload=reload,
    )


# For development/testing
if __name__ == "__main__":
    main()
