import logging
import subprocess
import platform
from logging.handlers import RotatingFileHandler
from colorlog import ColoredFormatter
import colorama


# Initialize colorama for Windows CMD support
colorama.init()


def setup_logger(
    name: str = "default_logger",
    log_file: str = "default_logger.log",
    level: str = "DEBUG",
    use_console: bool = True,
) -> logging.Logger:
    """
    Sets up a logger with console and file handlers, with optional colors for console output.
    Args:
        name (str): Name of the logger.
        log_file (str): File to store logs.
        level (str): Logging level (e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL).
        use_console (bool): Whether to enable the console handler.
    Returns:
        logging.Logger: Configured logger instance.
    """
    # Map string level to logging level constants
    level = getattr(logging, level.upper(), logging.DEBUG)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Formatter for file logs
    file_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Formatter for console logs (with colors)
    console_formatter = ColoredFormatter(
        "%(log_color)s[%(asctime)s] %(levelname)s in %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        },
    )

    # File Handler with rotation
    file_handler = RotatingFileHandler(log_file, maxBytes=10_000_000, backupCount=3)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Optional Console Handler
    if use_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger


def open_log_console(log_file: str = "default_logger.log"):
    """
    Opens a new console window to display logs in real time.
    Args:
        log_file (str): The log file to be streamed in the new console.
    """
    if platform.system() == "Windows":
        # Windows command to open a new console and tail the log file
        subprocess.Popen(
            f'start cmd /k "powershell Get-Content {log_file} -Wait"',
            shell=True,
        )
    elif platform.system() == "Darwin":  # macOS
        # macOS command to open a new terminal and tail the log file
        subprocess.Popen(
            [
                "osascript",
                "-e",
                f'tell application "Terminal" to do script "tail -f {log_file}"',
            ]
        )
    elif platform.system() == "Linux":
        # Linux command to open a new terminal and tail the log file
        subprocess.Popen(["gnome-terminal", "--", "tail", "-f", log_file])
    else:
        print("Unsupported platform for opening a log console.")


# Example usage (this will only execute if run directly)
if __name__ == "__main__":
    # Start with console logging enabled
    logger = setup_logger()

    logger.debug("This is a debug message.")
    logger.info("This is an info message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")
    logger.critical("This is a critical message.")

    # Open a new console for logs and disable logging to the main program console
    open_log_console()
    logger = setup_logger(use_console=False)

    # Only file logs will be written now
    logger.info("This log will only appear in the file and the log console.")
