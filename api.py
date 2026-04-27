import sys


def main():
    try:
        import uvicorn
    except ImportError:
        print("Missing dependency: uvicorn")
        print("Install with: python3 -m pip install fastapi uvicorn")
        sys.exit(1)

    try:
        from app.config import settings
    except ImportError as exc:
        print(f"Backend import failed: {exc}")
        sys.exit(1)

    print(f"API running at http://{settings.api_host}:{settings.api_port}")
    print(f"POST endpoint: http://{settings.api_host}:{settings.api_port}/telegram-ingest")
    print(f"Health check: http://{settings.api_host}:{settings.api_port}/health")
    print(f"Storage folder: {settings.storage_dir}")
    print(f"CSV file: {settings.reel_urls_csv}")
    print("Press Control+C to stop.")
    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, reload=False)


if __name__ == "__main__":
    main()
