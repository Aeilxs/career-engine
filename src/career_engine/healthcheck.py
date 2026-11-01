"""Small healthcheck without adding curl to the runtime image."""

from urllib.request import urlopen


def main() -> None:
    with urlopen("http://127.0.0.1:8000/healthz", timeout=3) as response:
        if response.status != 200:
            raise RuntimeError(f"Health endpoint returned {response.status}")


if __name__ == "__main__":
    main()
