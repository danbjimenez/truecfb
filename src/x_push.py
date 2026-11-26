"""TrueCFB reply bot: have X push each mention of @truecfb to the Worker the moment it happens
(X Activity API, event post.mention.create) instead of the Worker asking every few minutes.

  x_push.py status    the webhooks and Activity subscriptions on the app
  x_push.py setup     register https://truecfb.com/hooks/x (X checks it right away with the Worker's
                      X_CLIENT_SECRET) and subscribe it to mentions of @truecfb
  x_push.py remove    delete the mention subscription and the webhook (the Worker's backup check of
                      the mentions keeps working)

Run from the "Reply bot: set up push" job. Environment: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN,
X_ACCESS_SECRET (the app and @truecfb's OAuth 1.0a keys, already in GitHub), X_USER_ID.
Webhooks use the app's own token (from the API key and secret); the subscription is made as @truecfb.
"""
import os
import sys

import requests
from requests_oauthlib import OAuth1

API = "https://api.x.com/2"
HOOK = "https://truecfb.com/hooks/x"
EVENT = "post.mention.create"
TAG = "truecfb-mentions"


def app_token():
    """The app-only bearer token, from the app's API key and secret (OAuth 2.0 client credentials)."""
    r = requests.post("https://api.x.com/oauth2/token", timeout=30, data={"grant_type": "client_credentials"},
                      auth=(os.environ["X_API_KEY"], os.environ["X_API_SECRET"]))
    if r.status_code != 200:
        sys.exit(f"could not get the app token: {r.status_code} {r.text[:200]}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def user_auth():
    return OAuth1(os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
                  os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_SECRET"])


def show(r):
    return f"{r.status_code} {r.text[:400]}"


def webhooks(app):
    r = requests.get(f"{API}/webhooks", headers=app, timeout=30)
    if r.status_code != 200:
        sys.exit(f"could not list webhooks: {show(r)}")
    return r.json().get("data") or []


def subscriptions(auth=None, headers=None):
    r = requests.get(f"{API}/activity/subscriptions", auth=auth, headers=headers, timeout=30)
    if r.status_code != 200:
        print(f"could not list subscriptions: {show(r)}")
        return []
    return r.json().get("data") or []


def status():
    app = app_token()
    hooks = webhooks(app)
    print("webhooks:", hooks or "none")
    subs = subscriptions(headers=app) or subscriptions(auth=user_auth())
    print("subscriptions:", subs or "none")
    return app, hooks, subs


def setup():
    uid = os.environ.get("X_USER_ID", "").strip()
    if not uid.isdigit():
        sys.exit("X_USER_ID is not set (a GitHub variable)")
    app, hooks, subs = status()
    hook = next((h for h in hooks if h.get("url") == HOOK), None)
    if hook is None:
        r = requests.post(f"{API}/webhooks", headers=app, json={"url": HOOK}, timeout=60)
        if r.status_code not in (200, 201):
            sys.exit(f"X would not register {HOOK}: {show(r)}\n"
                     "If the reason is CrcValidationFailed: check that X_CLIENT_SECRET in Cloudflare is the app's "
                     "OAuth 2.0 client secret, and that the Worker has deployed.")
        hook = r.json()["data"]
        print("registered webhook", hook)
    elif not hook.get("valid"):
        r = requests.put(f"{API}/webhooks/{hook['id']}", headers=app, timeout=60)
        print("asked X to check the webhook again:", show(r))
    else:
        print("webhook already registered and valid:", hook["id"])
    if any(s.get("event_type") == EVENT and str((s.get("filter") or {}).get("user_id")) == uid for s in subs):
        print("already subscribed to mentions of @truecfb")
        return
    body = {"event_type": EVENT, "filter": {"user_id": uid}, "webhook_id": hook["id"], "tag": TAG}
    # Mentions are a private event: X wants the subscription made as the account itself.
    r = requests.post(f"{API}/activity/subscriptions", auth=user_auth(), json=body, timeout=60)
    if r.status_code in (200, 201):
        print("subscribed:", r.json().get("data"))
        return
    sys.exit(f"X would not subscribe with @truecfb's keys: {show(r)}\n"
             "X may want an OAuth 2.0 sign-in by @truecfb for this (scope tweet.read). See docs/REPLY-BOT.md.")


def remove():
    app, hooks, subs = status()
    for s in subs:
        if s.get("event_type") == EVENT:
            sid = s.get("subscription_id") or s.get("id")
            r = requests.delete(f"{API}/activity/subscriptions/{sid}", auth=user_auth(), timeout=30)
            print("removed subscription", sid, show(r))
    for h in hooks:
        if h.get("url") == HOOK:
            r = requests.delete(f"{API}/webhooks/{h['id']}", headers=app, timeout=30)
            print("removed webhook", h["id"], show(r))


if __name__ == "__main__":
    {"status": status, "setup": setup, "remove": remove}.get(
        sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
