import os
from flask import request
from dotenv import load_dotenv

load_dotenv()


def auth(api, apikey=os.getenv('X_API_KEY')):
    def _authorize(func):
        def check_auth(*args, **kwargs):
            headers = request.headers
            auth = headers.get("X-Api-Key")
            if auth != apikey:
                api.abort(401, 'API key required')
            return func(*args, **kwargs)

        return check_auth
    return _authorize
