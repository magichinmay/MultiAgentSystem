from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message
import asyncio
import json

class AMR1(Agent):
    class AMRFSM(FSMBehaviour):
        async def on_start(self):
            print("AMR1 FSM started.")

        async def on_end(self):
            print("AMR1 FSM finished.")

    class Idle(State):
        async def run(self):
            print("State: Idle. Waiting for coordinates or breakdown signal...")
            msg = await self.receive(timeout=10)  # Wait for a message with a 10-second timeout
            if msg:
                performative = msg.get_metadata("performative")
                if performative == "request" and msg.body == "status_check":
                    # Respond with "Idle" state
                    reply = Message(to=str(msg.sender))  # Convert sender to string explicitly
                    reply.set_metadata("performative", "inform")
                    reply.body = "Idle"
                    await self.send(reply)
                    print("Sent Idle status to SchedulerAgent.")
                    self.set_next_state("Idle")
                elif performative == "inform":
                    try:
                        coordinates = json.loads(msg.body)  # Deserialize the received JSON message
                        if isinstance(coordinates, float):  # Ensure it's a valid coordinate
                            print(f"Received coordinates: {coordinates}")
                            self.agent.coordinates = coordinates  # Store coordinates for later processing
                            self.set_next_state("Processing")
                        else:
                            print("Error: Received data is not a valid coordinate.")
                            self.set_next_state("Idle")
                    except json.JSONDecodeError:
                        print("Error: Unable to decode message body as JSON.")
                        self.set_next_state("Idle")
                else:
                    print("Unrecognized message type.")
                    self.set_next_state("Idle")
            else:
                print("No message received. Remaining in Idle state.")
                self.set_next_state("Idle")

    class Processing(State):
        async def run(self):
            print(f"State: Processing. Processing coordinates: {self.agent.coordinates}")
            await asyncio.sleep(15)  # Simulate processing for 15 seconds
            print(f"Finished processing coordinates: {self.agent.coordinates}")
            self.set_next_state("Idle")  # Return to Idle after processing

    class Breakdown(State):
        async def run(self):
            print("State: Breakdown. Sending JID of assistance agent...")
            msg = Message(to="robot2@jabber.fr")  # JID of another agent
            msg.set_metadata("performative", "inform")
            msg.body = "Breakdown: please assist."
            
            await self.send(msg)
            print("Breakdown message sent to another agent.")
            self.set_next_state("Idle")  # Go back to Idle state after breakdown

    async def setup(self):
        # Initialize FSM
        fsm = self.AMRFSM()

        # Add states to FSM
        fsm.add_state(name="Idle", state=self.Idle(), initial=True)
        fsm.add_state(name="Processing", state=self.Processing())
        fsm.add_state(name="breakdown", state=self.Breakdown())

        # Define transitions between states
        fsm.add_transition(source="Idle", dest="Processing")
        fsm.add_transition(source="Idle", dest="breakdown")
        fsm.add_transition(source="Processing", dest="Idle")
        fsm.add_transition(source="breakdown", dest="Idle")

        # Add FSM to the agent
        self.add_behaviour(fsm)

if __name__ == "__main__":
    amr1 = AMR1("robot1@jabber.fr", "changeme")

    async def run():
        await amr1.start()
        print("AMR1 started")

        try:
            while amr1.is_alive():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await amr1.stop()

    asyncio.run(run())
