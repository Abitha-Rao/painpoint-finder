"""Save your Reddit API keys to .env and test them. Nothing is shown on screen or sent anywhere
except Reddit's own login endpoint.

  .venv/bin/python setup_reddit.py

Get the keys first: log in to Reddit, open https://www.reddit.com/prefs/apps, create an app
of type "script" (redirect uri http://localhost:8080). The client id is the short string
under the app name; the secret is labelled "secret".
"""
import getpass
import os
import sys

import requests

from pf.common import ROOT, USER_AGENT


def main():
    print("Paste each value and press Enter. Typing is hidden.")
    cid = getpass.getpass("Reddit client id: ").strip().strip("\"'")
    secret = getpass.getpass("Reddit secret: ").strip().strip("\"'")
    if not cid or not secret:
        sys.exit("Nothing saved: both values are needed.")
    try:
        r = requests.post("https://www.reddit.com/api/v1/access_token", auth=(cid, secret),
                          data={"grant_type": "client_credentials"},
                          headers={"User-Agent": USER_AGENT}, timeout=20)
        ok = r.status_code == 200 and "access_token" in r.json()
    except Exception as e:
        sys.exit(f"Could not reach Reddit ({type(e).__name__}). Nothing saved.")
    if not ok:
        sys.exit(f"Reddit rejected these keys (HTTP {r.status_code}). Nothing saved. "
                 "Check the app type is 'script' and that you copied the id and secret, not the app name.")
    env = ROOT / ".env"
    env.write_text(f"REDDIT_CLIENT_ID={cid}\nREDDIT_CLIENT_SECRET={secret}\n")
    os.chmod(env, 0o600)  # readable only by you
    print(f"Keys work and are saved to {env} (kept out of git by .gitignore).")


if __name__ == "__main__":
    main()
