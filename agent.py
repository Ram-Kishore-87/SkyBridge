import asyncio
import os
import sys

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

if "GEMINI_API_KEY" not in os.environ:
    raise RuntimeError("GEMINI_API_KEY is not set in your environment.")

def check_flight_status(flight_number: str) -> str:
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
    mock_alternates = {
        ("DEL", "BLR"): ["AI-204 (departs 2hrs later)", "6E-310 (departs 4hrs later)"],
        ("BOM", "HYD"): ["UK-880 (departs tomorrow 6am)"],
    }
    key = (origin.upper(), destination.upper())
    options = mock_alternates.get(key)
    if not options:
        return f"No alternate flights found between {origin} and {destination}."
    return f"Alternate flights {origin}->{destination}: " + "; ".join(options)

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

async def ainput(prompt: str) -> str:
    print(prompt, end="", flush=True)
    return await asyncio.to_thread(sys.stdin.readline)

APP_NAME = "skybridge_app"
USER_ID = "operator_01"

async def main():
    print("--- SKYBRIDGE RUNTIME INITIALIZED ---", flush=True)
    print("Type 'exit' to quit. Each question is independent (no memory).\n", flush=True)

    session_service = InMemorySessionService()
    runner = Runner(
        agent=rebooking_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    turn_counter = 0

    while True:
        user_input = await ainput("[YOU]: ")
        user_input = user_input.strip()

        if user_input.lower() == "exit":
            print("Session terminated.", flush=True)
            break

        if not user_input:
            continue

        turn_counter += 1
        session_id = f"turn_{turn_counter}"

        await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=session_id,
        )

        user_message = types.Content(
            role="user",
            parts=[types.Part(text=user_input)],
        )

        print(f"\n[{rebooking_agent.name.upper()} PROCESSING]...", flush=True)

        try:
            async for event in runner.run_async(
                user_id=USER_ID,
                session_id=session_id,
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
