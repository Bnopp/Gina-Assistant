from config.settings import Config
from gina.assistant import Assistant

def main() -> None:
    """
    Main entry point for the application.
    """

    print(f"Gina - Version {Config.get_version()}")

    assistant.set_persona(persona="Gina")

    user_input = input("User: ")
    while user_input != "exit":
        assistant.send_message(role="user", message=user_input)
        user_input = input("User: ")


if __name__ == '__main__':
    Config._load_config_file()

    assistant: Assistant = Assistant()

    main()
