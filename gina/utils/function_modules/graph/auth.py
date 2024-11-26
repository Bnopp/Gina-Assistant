import os
import msal
import pyperclip
import webbrowser
from typing import Any, List
from logging import Logger
from gina.utils.logger import setup_logger
from gina.decorators.singleton import singleton

logger: Logger = setup_logger()

@singleton
class GraphAuthenticator:
    def __init__(self, app_id: str, scopes: list[str]) -> None:
        self.SCOPES: list[str] = scopes
        self.token_cache: msal.SerializableTokenCache = msal.SerializableTokenCache()

        if os.path.exists("token_cache.json"):
            with open("token_cache.json", "r") as f:
                self.token_cache.deserialize(f.read())
        
        self.client = msal.PublicClientApplication(client_id=app_id, token_cache=self.token_cache)
        self.token: dict = self.generate_token(app_id, scopes)

    def generate_token(self, app_id: str, scopes: list[str]) -> dict:
        self.token_cache = msal.SerializableTokenCache()

        if os.path.exists("token_cache.json"):
           self.token_cache.deserialize(open("token_cache.json", "r").read())
        
        client: msal.ClientApplication = msal.PublicClientApplication(client_id=app_id, token_cache=self.token_cache)

        accounts: List[dict[str, Any]] = client.get_accounts()
        if accounts:
            token_response: dict = client.acquire_token_silent(scopes, account=accounts[0])
        else:
            flow: msal.PublicClientApplication = client.initiate_device_flow(scopes=scopes)
            pyperclip.copy(flow["user_code"])
            webbrowser.open(flow["verification_uri"])

            token_response: dict = client.acquire_token_by_device_flow(flow)
        
        with open("token_cache.json", "w") as f:
            f.write(self.token_cache.serialize())
        


        return token_response

if __name__ == "__main__":
    app_id: str = "252e9e83-60c2-4b55-8525-e4278885346e"
    scopes: list[str] = ["User.Read"]

    auth: GraphAuthenticator = GraphAuthenticator(app_id, scopes)
