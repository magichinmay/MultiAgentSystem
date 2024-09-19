from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import asyncio
import json

class SchedulerAgent(Agent):
    class SchedulerBehaviour(CyclicBehaviour):
        def __init__(self):
            super().__init__()
            self.coordinates = [1.0, 2.0, 3.0, 4.0]  # Example list of coordinates
            self.index = 0  # Keep track of which coordinate to send
            self.waiting_for_idle = False  # Flag to track waiting for idle response

        async def run(self):
            if not self.waiting_for_idle:
                # Send a query to check if AMR1 is in "Idle" state
                msg = Message(to="robot1@jabber.fr")  # JID of the AMR1 agent
                msg.set_metadata("performative", "request")  # Requesting the state
                msg.body = "status_check"
                await self.send(msg)
                print("Sent status check to AMR1")
                self.waiting_for_idle = True  # Wait for a response before sending coordinates

            # Listen for a response
            response = await self.receive(timeout=10)  # Wait for 10 seconds for a response
            if response:
                if response.body == "Idle":
                    # AMR1 is idle, send the next coordinate
                    point = self.coordinates[self.index]
                    msg = Message(to="robot1@jabber.fr")  # JID of the AMR1 agent
                    msg.set_metadata("performative", "inform")
                    msg.body = json.dumps(point)  # Convert the coordinate to JSON string
                    await self.send(msg)
                    print(f"Sending coordinate: {point} to AMR1")

                    # Update index for next coordinate
                    self.index = (self.index + 1) % len(self.coordinates)

                    await asyncio.sleep(5)  # Wait before sending the next point
                else:
                    print("AMR1 is not in Idle state, retrying...")
                self.waiting_for_idle = False  # Reset to send the next query
            else:
                print("No response from AMR1, will retry after some time.")
                await asyncio.sleep(5)  # Wait before checking again

    async def setup(self):
        scheduler_behaviour = self.SchedulerBehaviour()
        self.add_behaviour(scheduler_behaviour)

if __name__ == "__main__":
    scheduler_agent = SchedulerAgent("scheduler@jabber.fr", "changeme")

    async def run():
        await scheduler_agent.start()
        print("SchedulerAgent started")

        try:
            while scheduler_agent.is_alive():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await scheduler_agent.stop()

    asyncio.run(run())
