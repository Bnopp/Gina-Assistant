from gina.utils.openai.openai_service import OpenAIService


class Assistant:
    """
    Assistant class to interact with OpenAI API
    """
    
    def __init__(self) -> None:
        self.openai_service = OpenAIService()

    def set_persona(self, persona: str = "") -> None:
        """
        Set persona for the conversation
        """
        self.openai_service.set_persona(persona=persona)

    def send_message(self, role: str = "user", message: str = "") -> str:
        """
        Send message to OpenAI API
        """

        # Add message to OpenAI service
        self.openai_service.add_message(role=role, message=message)

        # Define a callback to handle the streaming output
        def stream_printer(content: str):
            print(content, end="", flush=True)  # Print without a newline

        # Call get_completion with the callback
        response = self.openai_service.get_completion(stream_callback=stream_printer)

        print()
        return response
