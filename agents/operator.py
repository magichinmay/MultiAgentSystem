import asyncio
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from spade.message import Message

class OperatorAgent(Agent):
    class BreakdownBehaviour(OneShotBehaviour):
        async def run(self):
            print("Operator Agent is ready to send breakdown messages.")
            
            while True:
                user_input = input("Enter 'Breakdown' to notify robots: ")
                
                if user_input == "Breakdown":
                    # Creating the message
                    msg = Message(to="robot1@jabber.fr")  # Replace with robot's address
                    msg.set_metadata("performative", "user_input")  # Performative type
                    msg.body = "Breakdown"  # Message content

                    # Send the message
                    await self.send(msg)
                    print("Breakdown message sent to robot.")

                elif user_input == "exit":
                    print("Exiting Operator Agent...")
                    break
                else:
                    print("Invalid input. Please type 'Breakdown' or 'exit'.")

    async def setup(self):
        print("Operator Agent starting...")
        breakdown_behaviour = self.BreakdownBehaviour()
        self.add_behaviour(breakdown_behaviour)

async def main():
    # Replace "operator@domain" and "password" with your credentials
    operator_agent = OperatorAgent("useragent@jabber.fr", "changeme")
    await operator_agent.start()  # Correctly await the coroutine

    print("Press Ctrl+C to stop the agent.")
    try:
        while operator_agent.is_alive():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Stopping Operator Agent...")
        await operator_agent.stop()  # Properly await stop coroutine

if __name__ == "__main__":
    asyncio.run(main())  # Use asyncio.run to handle the event loop
