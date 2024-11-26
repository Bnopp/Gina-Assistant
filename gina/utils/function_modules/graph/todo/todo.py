import requests
from config.settings import Config
from gina.decorators.singleton import singleton

@singleton
class ToDo:

    def __init__(self, access_token: dict) -> None:
        self.BASE_ENDPOINT: str = Config.get_config_value("graph_endpoint") + "/me/todo"
        self.ACCESS_TOKEN: dict = access_token
        self.default_headers: dict = {
            'Authorization': 'Bearer ' + self.ACCESS_TOKEN
        }
    
    async def get_lists(self) -> dict[int, str]:
        endpoint: str = self.BASE_ENDPOINT + "/lists"
        
        reponse: requests.Response = requests.get(endpoint, headers=self.default_headers)

        lists: dict[str, int] = {}

        for list in reponse.json()['value']:
            lists[list['displayName']] = list['id']
        
        return lists
    
    async def get_tasks(self, list_id: str) -> dict:
        endpoint: str = self.BASE_ENDPOINT + "/lists/" + list_id + "/tasks"

        response: requests.Response = requests.get(endpoint, headers=self.default_headers)

        return response.json()['value']
    
    async def get_tasks_with_name(self, list_name: str) -> dict:
        # ToDO: Implement method to get tasks by list name instead of list id
        pass

