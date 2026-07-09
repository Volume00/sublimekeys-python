"""Minimal end-to-end example: run this once to activate, run it again to
see the second call resolve entirely from the offline cache."""

from sublimekeys import SublimeKeysClient

PRODUCT_ID = "my-app"  # replace with your own product slug from the dashboard


def main():
    client = SublimeKeysClient(product_id=PRODUCT_ID)
    license_key = input("Enter your license key: ").strip()

    result = client.activate(license_key)
    if not result.valid:
        print(f"Activation failed: {result.message}")
        return

    print(f"Activated. Machine id: {client.get_machine_id()}")

    # Simulates the app's next launch.
    result = client.verify(license_key)
    print(f"Verify result: valid={result.valid} source={result.source}")


if __name__ == "__main__":
    main()
