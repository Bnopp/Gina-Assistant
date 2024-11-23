from dotenv import load_dotenv
from config.settings import Config

config: Config = Config()

load_dotenv()

def main() -> None:
    """
    Main entry point for the application.
    """
    print(f"Gina - Version {config.get_version()}")


if __name__ == '__main__':
    main()
