import argparse
import getpass
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone

from .crypto import encrypt_secret
from .server import create_app, start_cleanup_thread, store_secret


def parse_duration(s: str) -> timedelta:
    m = re.fullmatch(r"(\d+)\s*(h|m)", s.strip())
    if not m:
        raise argparse.ArgumentTypeError(
            f"Invalid duration '{s}'. Use format like 1h, 30m, 24h."
        )
    value, unit = int(m.group(1)), m.group(2)
    if unit == "h":
        return timedelta(hours=value)
    return timedelta(minutes=value)


def main():
    parser = argparse.ArgumentParser(
        prog="ess",
        description="Share secrets via one-time links. Client-side encrypted.",
    )
    parser.add_argument("secret", nargs="?", help="The secret text to share.")
    parser.add_argument(
        "--expires", "-e", type=parse_duration, default=None,
        help="Time until the secret expires (e.g., 1h, 30m, 24h).",
    )
    parser.add_argument(
        "--port", "-p", type=int, default=8080,
        help="Port to run the server on (default: 8080).",
    )
    args = parser.parse_args()

    # Get the secret
    if args.secret:
        secret = args.secret
    elif not sys.stdin.isatty():
        secret = sys.stdin.read().rstrip("\n")
    else:
        secret = getpass.getpass("Enter secret: ")

    if not secret:
        print("Error: No secret provided.", file=sys.stderr)
        sys.exit(1)

    # Encrypt
    secret_id = uuid.uuid4().hex[:8]
    ciphertext_b64, key_b64url = encrypt_secret(secret)

    # Compute expiry
    expires_at = None
    if args.expires:
        expires_at = datetime.now(timezone.utc) + args.expires

    # Store
    store_secret(secret_id, ciphertext_b64, expires_at)

    # Build link
    link = f"http://localhost:{args.port}/s/{secret_id}#{key_b64url}"

    print()
    print("\U0001f512 Secret encrypted and stored.")
    print()
    print("Share this link (one-time use):")
    print(f"  {link}")
    print()
    if args.expires:
        total_seconds = int(args.expires.total_seconds())
        if total_seconds >= 3600:
            label = f"{total_seconds // 3600} hour{'s' if total_seconds >= 7200 else ''}"
        else:
            label = f"{total_seconds // 60} minute{'s' if total_seconds >= 120 else ''}"
        print(f"\u23f1 Expires in {label} if not viewed.")
        print()
    print(f"Server running on port {args.port} \u2014 press Ctrl+C to stop.")
    print("Waiting for secret to be viewed...")

    # Start cleanup thread and server
    start_cleanup_thread()
    app = create_app()

    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.WARNING)

    try:
        app.run(host="0.0.0.0", port=args.port)
    except KeyboardInterrupt:
        print("\nServer stopped.")
