"""Generate a Gmail API refresh token for the task notification sender."""

import argparse
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Authorize Gmail API and print a refresh token for Render."
    )
    parser.add_argument(
        "client_secrets",
        type=Path,
        help="Path to the downloaded Google OAuth desktop client JSON file.",
    )
    args = parser.parse_args()

    if not args.client_secrets.is_file():
        raise SystemExit(f"OAuth client file not found: {args.client_secrets}")

    flow = InstalledAppFlow.from_client_secrets_file(
        str(args.client_secrets),
        scopes=[GMAIL_SEND_SCOPE],
    )
    credentials = flow.run_local_server(
        host="localhost",
        port=0,
        access_type="offline",
        prompt="consent",
    )

    print("\nAdd this value to Render as GMAIL_REFRESH_TOKEN:\n")
    print(credentials.refresh_token)
    print("\nThe token belongs to the Gmail account you authorized.")


if __name__ == "__main__":
    main()
