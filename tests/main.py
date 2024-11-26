import json
import asyncio
from gina.utils.function_modules.graph.todo.todo import ToDo
from gina.utils.function_modules.graph.auth import GraphAuthenticator

async def main():
    auth: GraphAuthenticator = GraphAuthenticator("252e9e83-60c2-4b55-8525-e4278885346e", ["User.Read"])
    todo: ToDo = ToDo(auth.token['access_token'])

    lists: dict[int, str] = await todo.get_lists()
    
    tasks = await todo.get_tasks(lists['Tasks'])

    with open("tests/tasks.json", "w") as f:
        f.write(json.dumps(tasks, indent=4))


if __name__ == "__main__":
    asyncio.run(main())
