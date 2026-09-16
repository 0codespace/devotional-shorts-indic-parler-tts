#!/usr/bin/env python3
import json, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path

cfg_path = Path(__file__).with_name('yt_config.json')
try:
    cfg = json.loads(cfg_path.read_text())
    body = urllib.parse.urlencode({
        'client_id': cfg['client_id'],
        'client_secret': cfg['client_secret'],
        'refresh_token': cfg['refresh_token'],
        'grant_type': 'refresh_token',
    }).encode()
    req = urllib.request.Request('https://oauth2.googleapis.com/token', data=body, method='POST')
    with urllib.request.urlopen(req, timeout=20) as response:
        data = json.loads(response.read())
    if not data.get('access_token'):
        raise RuntimeError('Google token response did not include access_token')
    print(json.dumps({'status': 'ok', 'expires_in': data.get('expires_in')}))
except urllib.error.HTTPError as exc:
    detail = exc.read().decode(errors='replace')
    try: err = json.loads(detail).get('error', 'http_error')
    except Exception: err = 'http_error'
    if err == 'invalid_grant':
        print(json.dumps({'status': 'failed', 'reason': 'oauth_reauth_required', 'detail': 'YouTube refresh token is expired or revoked'}))
    else:
        print(json.dumps({'status': 'failed', 'reason': 'oauth_preflight_http_error', 'detail': f'HTTP {exc.code}', 'google_error': err}))
    sys.exit(1)
except Exception as exc:
    print(json.dumps({'status': 'failed', 'reason': 'oauth_preflight_unavailable', 'detail': str(exc)[:240]}))
    sys.exit(2)
