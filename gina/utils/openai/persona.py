import json
from dataclasses import dataclass
from typing import List
from config.settings import Config

@dataclass
class Persona:
    name: str
    description: str

def load_personas() -> List[Persona]:
    """
    Load personas from file
    """
    file_path = Config.get_config_value(key="personas_path")

    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    
    return [
        Persona(name=persona["name"], description=persona["description"])
        for persona in data
    ]
