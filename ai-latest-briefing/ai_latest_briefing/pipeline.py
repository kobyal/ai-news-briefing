"""ADK pipeline runner for AI Latest Briefing."""
import asyncio

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .agent import root_agent


async def _run_async():
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="briefing", user_id="u1")
    runner = Runner(agent=root_agent, app_name="briefing", session_service=session_service)
    msg = types.Content(role="user", parts=[types.Part(text="Run the latest briefing")])
    async for event in runner.run_async(user_id="u1", session_id=session.id, new_message=msg):
        if event.is_final_response():
            print(event.content)


def run_pipeline():
    asyncio.run(_run_async())
