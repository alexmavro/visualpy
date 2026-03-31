"""Minimal test fixture — a simple script with clear structure."""

import os
import json
import requests


API_KEY = os.getenv("MY_API_KEY")


def fetch_data(url: str) -> dict:
    """Fetch JSON data from a URL."""
    response = requests.get(url, headers={"Authorization": f"Bearer {API_KEY}"})
    return response.json()


def save_results(data: dict, path: str = "output.json") -> None:
    """Save results to a JSON file."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def main(url: str, output: str = "output.json", verbose: bool = False):
    """Fetch data from API and save to file."""
    if verbose:
        print(f"Fetching from {url}...")

    data = fetch_data(url)

    if verbose:
        print(f"Got {len(data)} items")

    save_results(data, output)
    print(f"Saved to {output}")


if __name__ == "__main__":
    main("https://api.example.com/data")
