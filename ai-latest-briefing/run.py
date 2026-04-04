"""Programmatic runner for AI Latest Briefing agent."""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from ai_latest_briefing.agent import root_agent


async def run():
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="briefing", user_id="u1")
    runner = Runner(agent=root_agent, app_name="briefing", session_service=session_service)
    msg = types.Content(role="user", parts=[types.Part(text="Run the latest briefing")])
    async for event in runner.run_async(user_id="u1", session_id=session.id, new_message=msg):
        if event.is_final_response():
            print(event.content)


if __name__ == "__main__":
    asyncio.run(run())
