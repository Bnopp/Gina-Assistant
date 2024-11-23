import os
import json
import inspect
import importlib
from logging import Logger
from config.settings import Config
from gina.utils.logger import setup_logger
from typing import Callable, List, Dict, Any

logger: Logger = setup_logger(__name__)

def import_methods_from_modules(modules_path: str = Config.get_config_value(key="functions_path")) -> Dict[str, Callable]:
    """
    Dynamically imports methods from Python modules located in the specified directory.

    Args:
        modules_path (str): The path to the directory containing Python modules.

    Returns:
        Dict[str, Callable]: A dictionary where the keys are method names and the values are method callables.
    """
    methods: Dict[str, Callable] = {}

    for root, dirs, files in os.walk(modules_path):
        for file in files:
            if file.endswith(".py"):
                # Build the module path and name
                module_path: str = os.path.join(root, file)
                module_name: str = (
                    module_path.replace("/", ".").replace("\\", ".").replace(".py", "")
                )

                # Attempt to import the module
                try:
                    module = importlib.import_module(module_name)
                except ImportError as e:
                    logger.error(f"Error importing module {module_name}: {e}")
                    continue

                # Get all classes in the module
                all_classes = inspect.getmembers(module, inspect.isclass)

                # Filter for the main class
                main_class = None
                for name, cls in all_classes:
                    if (
                        cls.__module__
                        == module.__name__  # Ensure class is from this module
                        and not inspect.isabstract(cls)  # Skip abstract classes
                    ):
                        main_class = cls
                        break

                if main_class:
                    try:
                        # Try to create an instance of the main class
                        instance = main_class()
                    except TypeError as e:
                        logger.error(f"Error creating instance of {main_class}: {e}")
                        continue

                    # Extract methods from the main class
                    for method_name, method in inspect.getmembers(
                        instance, inspect.isfunction
                    ):
                        if method_name != "__init__":
                            methods[method_name] = method

    return methods

def combine_tools_json(
    modules_path: str = Config.get_config_value(key="functions_path"),
    additional_tools: List[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Combines all `tools.json` files from a given directory and optionally appends additional tools.

    Args:
        modules_path (str): The path to the directory containing `tools.json` files.
        additional_tools (List[Dict[str, Any]], optional): A list of additional tools to append. Defaults to None.

    Returns:
        List[Dict[str, Any]]: A combined list of tools from all `tools.json` files and additional tools.
    """
    combined_tools: List[Dict[str, Any]] = []

    # Traverse the directory and find all tools.json files
    for root, dirs, files in os.walk(modules_path):
        for file in files:
            if file == "tools.json":
                file_path: str = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        tools: List[Dict[str, Any]] = json.load(f)
                        combined_tools.extend(tools)
                except (FileNotFoundError, json.JSONDecodeError) as e:
                    logger.error(f"Error loading tools from {file_path}: {e}")

    # Append additional tools if provided
    if additional_tools:
        combined_tools.extend(additional_tools)

    return combined_tools
