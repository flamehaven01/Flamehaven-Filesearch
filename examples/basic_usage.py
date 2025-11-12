"""
Basic usage example for FLAMEHAVEN FileSearch

This example demonstrates:
1. Initializing the searcher
2. Uploading a file
3. Searching for information
4. Handling results
"""

import json
import os

from flamehaven_filesearch import Config, FlamehavenFileSearch


def main():
    # Set API key (get from environment or set directly)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable")
        print("Example: export GEMINI_API_KEY='your-api-key'")
        return

    # Initialize FLAMEHAVEN FileSearch
    print("Initializing FLAMEHAVEN FileSearch...")
    searcher = FlamehavenFileSearch(api_key=api_key)

    # Example 1: Create a store
    print("\n1. Creating a store...")
    store_name = searcher.create_store("example-store")
    print(f"   Created store: {store_name}")

    # Example 2: Upload a file
    print("\n2. Uploading a file...")
    # Note: Replace with your actual file path
    file_path = "example_document.pdf"

    if os.path.exists(file_path):
        result = searcher.upload_file(file_path, store_name="example-store")
        print(f"   Upload status: {result['status']}")
        if result["status"] == "success":
            print(f"   File size: {result['size_mb']} MB")
    else:
        print(f"   File not found: {file_path}")
        print("   Please provide a valid file path")

    # Example 3: Search
    print("\n3. Searching for information...")
    query = "What are the main topics discussed in the document?"

    answer = searcher.search(query, store_name="example-store")

    if answer["status"] == "success":
        print(f"\n   Query: {answer['query']}")
        print(f"\n   Answer:\n   {answer['answer']}")
        print(f"\n   Model: {answer['model']}")

        if answer["sources"]:
            print(f"\n   Sources ({len(answer['sources'])}):")
            for i, source in enumerate(answer["sources"], 1):
                print(f"   {i}. {source['title']}")
                print(f"      URI: {source['uri']}")
        else:
            print("\n   No sources found")
    else:
        print(f"   Error: {answer.get('message', 'Unknown error')}")

    # Example 4: List all stores
    print("\n4. Listing all stores...")
    stores = searcher.list_stores()
    print(f"   Total stores: {len(stores)}")
    for name, resource in stores.items():
        print(f"   - {name}: {resource}")

    # Example 5: Get metrics
    print("\n5. Getting metrics...")
    metrics = searcher.get_metrics()
    print(f"   Metrics:\n{json.dumps(metrics, indent=2)}")


if __name__ == "__main__":
    main()
