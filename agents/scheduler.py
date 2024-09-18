from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import asyncio
import json

class SchedulerAgent(Agent):
    class SchedulerBehaviour(CyclicBehaviour):
        def __init__(self):
            super().__init__()
            self.breakdown_triggered = False  # Flag to check if "breakdown" was triggered
            self.coordinates = [1.0, 2.0, 3.0, 4.0]  # Example list of coordinates
            self.index = 0  # Index to track which coordinate to send

        async def run(self):
            if self.breakdown_triggered:
                # If "breakdown" was triggered, send "breakdown" message
                msg = Message(to="robot1@jabber.fr")  # JID of the AMR1 agent
                msg.set_metadata("performative", "inform")
                msg.body = "breakdown"
                await self.send(msg)
                print("Sending: 'breakdown' to robot1")
                self.breakdown_triggered = False  # Reset the flag
                await asyncio.sleep(5)  # Wait before the next cycle
            else:
                # Send coordinates cyclically
                point = self.coordinates[self.index]
                msg = Message(to="robot1@jabber.fr")  # JID of the AMR1 agent
                msg.set_metadata("performative", "inform")
                msg.body = json.dumps(point)  # Convert the coordinate to JSON string
                await self.send(msg)
                print(f"Sending coordinate: {point} to robot1")
                
                # Update index and reset if needed
                self.index = (self.index + 1) % len(self.coordinates)

                await asyncio.sleep(5)  # Wait 5 seconds before sending the next point

    async def setup(self):
        # Add the cyclic behaviour to send coordinates or handle breakdown
        scheduler_behaviour = self.SchedulerBehaviour()
        self.add_behaviour(scheduler_behaviour)

if __name__ == "__main__":
    scheduler_agent = SchedulerAgent("scheduler@jabber.fr", "changeme")

    async def run():
        await scheduler_agent.start()
        print("SchedulerAgent started")

        # Keep the agent running
        try:
            while scheduler_agent.is_alive():
                await asyncio.sleep(1)
                # Check user input in a non-blocking manner
                user_input = input("Enter 'breakdown' to trigger breakdown, or press Enter to continue: ").strip()
                if user_input.lower() == "breakdown":
                    print("Breakdown triggered!")
                    scheduler_agent.behaviours[0].breakdown_triggered = True
        except KeyboardInterrupt:
            await scheduler_agent.stop()

    asyncio.run(run())
