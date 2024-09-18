from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import asyncio

class ReceiverAgent(Agent):
    class ReceiverBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)  # Wait for a message with a 10-second timeout
            if msg:
                if msg.body == "Breakdown: please assist":
                    print("coming")
                else:
                    print(f"Received message: {msg.body}")
            else:
                print("No message received.")

    async def setup(self):
        # Add the cyclic behaviour to the agent
        receiver_behaviour = self.ReceiverBehaviour()
        self.add_behaviour(receiver_behaviour)

if __name__ == "__main__":
    receiver_agent = ReceiverAgent("robot2@jabber.fr", "changeme")

    async def run():
        await receiver_agent.start()
        print("ReceiverAgent started")

        # Keep the agent running
        try:
            while receiver_agent.is_alive():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await receiver_agent.stop()

    asyncio.run(run())
