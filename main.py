import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
import orchestrator

console = Console()


def run():
    console.print("\n[bold blue]CareDesk AI — Health Services Coordination[/bold blue]")
    console.print("[dim]Type your message below. Type 'quit' to exit.[/dim]\n")

    # First message
    first_message = console.input("[bold white]You:[/bold white] ").strip()
    if first_message.lower() == "quit":
        return

    context, reply, urgency_determined = orchestrator.start_conversation(first_message)
    console.print(f"\n[bold cyan]CareDesk:[/bold cyan] {reply}\n")

    # Intake loop
    while not urgency_determined:
        user_input = console.input("[bold white]You:[/bold white] ").strip()
        if user_input.lower() == "quit":
            return
        context, reply, urgency_determined = orchestrator.continue_intake(user_input, context)
        console.print(f"\n[bold cyan]CareDesk:[/bold cyan] {reply}\n")

    # First specialist response
    context, reply, done = orchestrator.route_to_specialist(context)
    console.print(f"\n[bold cyan]CareDesk:[/bold cyan] {reply}\n")

    # Specialist loop
    while not done:
        user_input = console.input("[bold white]You:[/bold white] ").strip()
        if user_input.lower() == "quit":
            return
        context, reply, done = orchestrator.next_specialist_turn(user_input, context)
        console.print(f"\n[bold cyan]CareDesk:[/bold cyan] {reply}\n")

    console.print("[bold green]Conversation complete. Confirmation sent to patient and care coordinator.[/bold green]\n")


if __name__ == "__main__":
    run()
