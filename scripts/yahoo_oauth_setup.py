import os
from yahoo_oauth import OAuth2

path = os.environ.get("YAHOO_OAUTH_JSON_PATH")
oauth = OAuth2(None, None, from_file=path)
print("token_valid:", oauth.token_is_valid())
print("oauth2.json should now contain access/refresh tokens.")