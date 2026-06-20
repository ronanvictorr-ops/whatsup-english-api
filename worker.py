import asyncio
import os

# Importing main configures the automation module with the existing domain
# services. It does not start a scheduler inside the web application.
import main as application
from wingo.automations import academic_automation_loop


def automations_enabled() -> bool:
    return os.getenv("ACADEMIC_AUTOMATIONS_ENABLED", "true").lower() == "true"


async def run_worker() -> None:
    if not automations_enabled():
        print("Academic automation worker disabled by ACADEMIC_AUTOMATIONS_ENABLED=false")
        return

    # Keep the module reference explicit: importing it performs dependency
    # wiring, while this process remains the sole owner of the scheduling loop.
    _ = application
    print("Academic automation worker started")
    await academic_automation_loop()


if __name__ == "__main__":
    asyncio.run(run_worker())
