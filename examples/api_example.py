"""
API client example for FLAMEHAVEN FileSearch

This example demonstrates how to interact with the FLAMEHAVEN FileSearch API server
using Python requests library.
"""

import json
from pathlib import Path

import requests


class FlamehavenAPIClient:
    """Simple API client for FLAMEHAVEN FileSearch"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    def health_check(self):
        """Check API health"""
        response = requests.get(f"{self.base_url}/health")
        return response.json()

    def upload_file(self, file_path: str, store: str = "default"):
        """Upload a file to the API"""
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {"store": store}
            response = requests.post(f"{self.base_url}/upload", files=files, data=data)
        return response.json()

    def upload_multiple_files(self, file_paths: list, store: str = "default"):
        """Upload multiple files"""
        files = [("files", open(fp, "rb")) for fp in file_paths]
        data = {"store": store}
        try:
            response = requests.post(
                f"{self.base_url}/upload-multiple", files=files, data=data
            )
            return response.json()
        finally:
            for _, f in files:
                f.close()

    def search(self, query: str, store: str = "default", model: str = None, **kwargs):
        """Search using POST method"""
        payload = {"query": query, "store_name": store}
        if model:
            payload["model"] = model
        payload.update(kwargs)

        response = requests.post(f"{self.base_url}/search", json=payload)
        return response.json()

    def search_get(self, query: str, store: str = "default"):
        """Search using GET method (simple)"""
        params = {"q": query, "store": store}
        response = requests.get(f"{self.base_url}/search", params=params)
        return response.json()

    def list_stores(self):
        """List all stores"""
        response = requests.get(f"{self.base_url}/stores")
        return response.json()

    def create_store(self, name: str):
        """Create a new store"""
        payload = {"name": name}
        response = requests.post(f"{self.base_url}/stores", json=payload)
        return response.json()

    def delete_store(self, name: str):
        """Delete a store"""
        response = requests.delete(f"{self.base_url}/stores/{name}")
        return response.json()

    def get_metrics(self):
        """Get API metrics"""
        response = requests.get(f"{self.base_url}/metrics")
        return response.json()


def main():
    """Example usage"""
    # Initialize client
    client = FlamehavenAPIClient("http://localhost:8000")

    print("FLAMEHAVEN FileSearch API Client Example")
    print("=" * 50)

    # 1. Health check
    print("\n1. Health Check")
    try:
        health = client.health_check()
        print(f"   Status: {health['status']}")
        print(f"   Version: {health['version']}")
    except Exception as e:
        print(f"   Error: {e}")
        print("   Make sure the API server is running!")
        print("   Start with: flamehaven-api")
        return

    # 2. Create a store
    print("\n2. Creating a store")
    try:
        result = client.create_store("api-example")
        print(f"   Result: {result['status']}")
    except Exception as e:
        print(f"   Error: {e}")

    # 3. Upload a file
    print("\n3. Uploading a file")
    # Note: Replace with your actual file
    file_path = "example_document.pdf"

    if Path(file_path).exists():
        try:
            result = client.upload_file(file_path, store="api-example")
            print(f"   Status: {result['status']}")
            if result["status"] == "success":
                print(f"   File: {result['file']}")
                print(f"   Size: {result['size_mb']} MB")
        except Exception as e:
            print(f"   Error: {e}")
    else:
        print(f"   File not found: {file_path}")

    # 4. Search (POST)
    print("\n4. Searching (POST method)")
    try:
        result = client.search(
            query="What are the main topics?",
            store="api-example",
            temperature=0.7,
            max_tokens=512,
        )
        if result["status"] == "success":
            print(f"   Answer: {result['answer'][:200]}...")
            print(f"   Sources: {len(result['sources'])} found")
        else:
            print(f"   Error: {result.get('message')}")
    except Exception as e:
        print(f"   Error: {e}")

    # 5. Search (GET)
    print("\n5. Searching (GET method)")
    try:
        result = client.search_get(query="summary", store="api-example")
        if result["status"] == "success":
            print(f"   Answer: {result['answer'][:200]}...")
        else:
            print(f"   Error: {result.get('message')}")
    except Exception as e:
        print(f"   Error: {e}")

    # 6. List stores
    print("\n6. Listing stores")
    try:
        result = client.list_stores()
        print(f"   Total stores: {result['count']}")
        for name in result["stores"]:
            print(f"   - {name}")
    except Exception as e:
        print(f"   Error: {e}")

    # 7. Get metrics
    print("\n7. Getting metrics")
    try:
        metrics = client.get_metrics()
        print(f"   Stores count: {metrics['stores_count']}")
        print(f"   Active stores: {metrics['stores']}")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 50)
    print("Example completed!")


if __name__ == "__main__":
    main()
