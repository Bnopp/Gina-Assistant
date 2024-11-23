import json
from logging import Logger
from openai import OpenAI, Stream
from config.settings import Config
from collections import defaultdict
from gina.decorators import singleton
from gina.utils.logger import setup_logger
from gina.utils.openai.persona import Persona, load_personas
from gina.utils.function_modules.functions import import_methods_from_modules, combine_tools_json

log_level: str = Config.get_config_value("log_level", "INFO")
logger: Logger = setup_logger(__name__)

@singleton
class OpenAIService:
    """
    OpenAI Wrapper Class around OpenAI API
    """

    def __init__(self) -> None:
        api_key: str = Config.get_env_variable(var_name="OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        
        self.client: OpenAI = OpenAI(api_key=api_key)
        self.messages: list[str] = []
        self.personas: list[Persona] = []
        self.function_dispatcher: dict[str, callable] = import_methods_from_modules()
        self.tools: list[dict[str, str]] = combine_tools_json()

        self._load_personas()
    
    def _load_personas(self) -> None:
        """
        Gets a list of personas
        """
        personas: list[Persona] = load_personas()

        self.personas = personas

        logger.debug(f"Loaded {len(personas)} persona(s)")
        logger.debug(f"Personas: {[persona.name for persona in personas]}")

    def set_persona(self, persona: str = "Default") -> None:
        """
        Set persona for the conversation
        """
        if persona:
            persona_obj: Persona = next(
                (p for p in self.personas if p.name.lower() == persona.lower()), None
            )

            if persona_obj:
                self.add_message(role="system", message=f"{persona_obj.description}")
                logger.debug(f"Set persona to {persona_obj.name}")
            else:
                logger.error(f"Persona {persona} not found")

    def add_message(self, role: str = "user", message: str = "") -> None:
        """
        Add message to the list of messages
        """
        self.messages.append({"role": role, "content": message})

    def _tool_list_to_tool_obj(self, tools):
        # Initialize a dictionary with default values
        tool_calls_dict = defaultdict(lambda: {"id": None, "function": {"arguments": "", "name": None}, "type": None})

        # Iterate over the tool calls
        for tool_call in tools:
            # If the id is not None, set it
            if tool_call.id is not None:
                tool_calls_dict[tool_call.index]["id"] = tool_call.id

            # If the function name is not None, set it
            if tool_call.function.name is not None:
                tool_calls_dict[tool_call.index]["function"]["name"] = tool_call.function.name

            # Append the arguments
            tool_calls_dict[tool_call.index]["function"]["arguments"] += tool_call.function.arguments

            # If the type is not None, set it
            if tool_call.type is not None:
                tool_calls_dict[tool_call.index]["type"] = tool_call.type

        # Convert the dictionary to a list
        tool_calls_list = list(tool_calls_dict.values())

        # Return the result
        return {"tool_calls": tool_calls_list}

    def get_completion(self, model: str = Config.get_config_value("default_LLM"), stream_callback = None) -> str:
        """
        Send message to OpenAI API
        """

        stream: Stream = self.client.chat.completions.create(
            model=model, 
            messages=self.messages,
            tools=self.tools,
            stream=True
        )

        response: str = ""
        tools: dict = []

        for chunk in stream:
            content = chunk.choices[0].delta.content
            if isinstance(content, str):
                response += content

                if stream_callback:
                    stream_callback(content)
            
            if chunk.choices[0].delta.tool_calls:
                tools += chunk.choices[0].delta.tool_calls

        tools = self._tool_list_to_tool_obj(tools)
        logger.debug(f"Tools: {tools}")

        if len(tools['tool_calls']) > 0:
            self.messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": tools["tool_calls"]
            })

            tool_outputs: dict = []
            for tool in tools['tool_calls']:
                function_name:str = tool['function']['name']
                function_args:str = tool['function']['arguments']

                func: callable = self.function_dispatcher.get(function_name)

                if func:
                    output = func(json.loads(function_args))
                    tool_outputs.append(output)
                    logger.debug(f"Tool {function_name} executed with arguments {function_args} and returned {output}")
                else:
                    logger.error(f"Function {function_name} not found")
                
                self.messages.append({
                    "role": "tool",
                    "content": json.dumps(output),
                    "name": function_name,
                    "tool_call_id": tool['id']
                })
        else:
            self.add_message(role="assistant", message=response)

        return response

    
    

    
        
