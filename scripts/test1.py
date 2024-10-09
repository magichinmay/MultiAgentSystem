from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import json
import asyncio

class SenderAgent(Agent):
    class SendMessageBehaviour(CyclicBehaviour):
        async def run(self):
            # Create a message to send
            msg = Message(to="machine2@jabber.fr")  # Change to the recipient's JID
            msg.body = json.dumps([1, 5])  # Send the list as a JSON string

            print(f"{self.agent.name}: Sending message: {msg.body}")
            await self.send(msg)  # Send the message
            
            # Wait for 5 seconds before sending the next message
            await asyncio.sleep(5)

    async def setup(self):
        print(f"{self.name}: Agent starting...")
        # Add the send message behavior to the agent
        self.add_behaviour(self.SendMessageBehaviour())

async def main():
    # Create and start the sender agent
    sender = SenderAgent("amr1@jabber.fr", "imagent1")  # Replace with the sender's JID and password
    await sender.start()

    # Keep the agent running for 30 seconds for testing
    await asyncio.sleep(30)

    # Stop the agent
    await sender.stop()

# Run the main function using asyncio
if __name__ == "__main__":
    asyncio.run(main())