import json, urllib.request, urllib.parse, subprocess, sys

CONFIG_PATH = "/home/ubuntu/devotional-shorts/yt_config.json"
try:
    cfg = json.load(open(CONFIG_PATH))
except Exception as e:
    print(f"Error loading {CONFIG_PATH}: {e}")
    sys.exit(1)

client_id = cfg["client_id"]
client_secret = cfg["client_secret"]

url = (
    "https://accounts.google.com/o/oauth2/v2/auth?"
    f"client_id={client_id}&"
    "redirect_uri=http://localhost:8901/&"
    "response_type=code&"
    "scope=https://www.googleapis.com/auth/youtube.upload&"
    "access_type=offline&"
    "prompt=consent"
)

print("\n=== STEP 1: SSH Port Forwarding ===")
print("Ensure you are connected to this server with port forwarding:")
print("  ssh -L 8901:127.0.0.1:8901 ubuntu@<server-ip>")

print("\n=== STEP 2: Authenticate ===")
print("Click the link below and authorize the application:")
print(url)
print("\nWaiting for redirect...")

try:
    subprocess.run(["python3", "/home/ubuntu/oauth_loopback_listener.py", "8901"], check=True)
except Exception as e:
    print(f"Listener failed: {e}")
    sys.exit(1)

try:
    code = open("/tmp/oauth_code.txt").read().strip()
except Exception:
    print("Could not read code from /tmp/oauth_code.txt")
    sys.exit(1)

if code.startswith("ERROR:"):
    print("Authentication failed:", code)
    sys.exit(1)

print("\n=== STEP 3: Exchanging code for refresh token ===")
body = urllib.parse.urlencode({
    "client_id": client_id,
    "client_secret": client_secret,
    "code": code,
    "grant_type": "authorization_code",
    "redirect_uri": "http://localhost:8901/"
}).encode()

req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body, method="POST")
try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
        if "refresh_token" in data:
            cfg["refresh_token"] = data["refresh_token"]
            with open(CONFIG_PATH, "w") as f:
                json.dump(cfg, f, indent=2)
            print("\nSUCCESS! yt_config.json updated with new refresh token.")
        else:
            print("\nResponse did not contain a refresh token. Make sure you included 'prompt=consent'.")
            print("Response:", data)
except Exception as e:
    print("\nError exchanging code:", e)
