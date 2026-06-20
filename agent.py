import asyncio
import os
import sys
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# --- API KEY CHECK ---
if "GEMINI_API_KEY" not in os.environ:
    raise RuntimeError("GEMINI_API_KEY is not set in your environment.")

# =====================================================================
# 1. TOOLS
# =====================================================================
def check_flight_status(flight_number: str) -> str:
    """
    Checks the live status of a flight in the airline's ops system.
    Args:
        flight_number: Flight code, e.g. AI-202
    """
    mock_flights = {
        "AI-202": {"status": "DELAYED", "reason": "weather at origin", "origin": "DEL", "destination": "BLR"},
        "6E-450": {"status": "CANCELLED", "reason": "technical fault", "origin": "BOM", "destination": "HYD"},
        "UK-101": {"status": "ON_TIME", "reason": None, "origin": "MAA", "destination": "DEL"},
    }
    record = mock_flights.get(flight_number.upper())
    if not record:
        return f"No record found for flight '{flight_number}'."
    if record["status"] == "ON_TIME":
        return f"Flight {flight_number} is ON TIME. No action needed."
    return f"Flight {flight_number} is {record['status']} due to {record['reason']}. Route: {record['origin']} -> {record['destination']}."


def find_alternate_flights(origin: str, destination: str) -> str:
    """
    Searches for alternate flights between two airport codes.
    Args:
        origin: Origin airport code, e.g. DEL
        destination: Destination airport code, e.g. BLR
    """
    mock_alternates = {
        ("DEL", "BLR"): ["AI-204 (departs 2hrs later)", "6E-310 (departs 4hrs later)"],
        ("BOM", "HYD"): ["UK-880 (departs tomorrow 6am)"],
    }
    key = (origin.upper(), destination.upper())
    options = mock_alternates.get(key)
    if not options:
        return f"No alternate flights found between {origin} and {destination}."
    return f"Alternate flights {origin}->{destination}: " + "; ".join(options)


# =====================================================================
# 2. AGENT BLUEPRINT
# =====================================================================
rebooking_agent = Agent(
    name="skybridge",
    model="gemini-2.5-flash",
    instruction=(
        "You are a flight operations assistant. Always check flight status first "
        "using check_flight_status. If the flight is DELAYED or CANCELLED, "
        "automatically call find_alternate_flights using the route from the status "
        "result, and recommend an alternate. If ON_TIME, just confirm and stop."
    ),
    tools=[check_flight_status, find_alternate_flights],
)

# =====================================================================
# 3. ASYNC INPUT HELPER FOR LINUX
# =====================================================================
async def ainput(prompt: str) -> str:
    """Non-blocking input function for async loops in Linux terminal"""
    print(prompt, end="", flush=True)
    line = await asyncio.to_thread(sys.stdin.readline)
    return line


# =====================================================================
# 4. RUNNER RUNTIME
# =====================================================================
APP_NAME = "skybridge_app"
USER_ID = "operator_01"
CONVERSATION_SESSION_ID = "active_operator_session_001"


async def main():
    print("--- SKYBRIDGE RUNTIME INITIALIZED ---")
    print("Type 'exit' to quit.\n")

    session_service = InMemorySessionService()
    runner = Runner(
        agent=rebooking_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    # Create the session ONCE before entering the loop
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=CONVERSATION_SESSION_ID,
    )

    while True:
        user_input = await ainput("[YOU]: ")
        user_input = user_input.strip()

        if not user_input:
            continue

        if user_input.lower() == "exit":
            print("Goodbye!")
            break

        user_message = types.Content(
            role="user",
            parts=[types.Part(text=user_input)],
        )

        print(f"\n[{rebooking_agent.name.upper()}]: ", end="", flush=True)

        try:
            async for event in runner.run_async(
                user_id=USER_ID,
                session_id=CONVERSATION_SESSION_ID,
                new_message=user_message,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            print(part.text, end="", flush=True)
            print("\n" + "-" * 50, flush=True)

        except Exception as e:
            print(f"\n[ERROR]: {e}\n" + "-" * 50, flush=True)


if __name__ == "__main__":
    asyncio.run(main())