from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message
import asyncio
import json
from math import inf

# States
IDLE = "IDLE"
PROCESSING = "PROCESSING"
WAITING="WAITING"

class MachineAgent(Agent):
    
    class MachineBehaviour(FSMBehaviour):
        async def on_start(self):
            print(f"{self.agent.name}: FSM starting")
            
        async def on_end(self):
            print(f"{self.agent.name}: FSM finished with state {self.current_state}")
    
    class IdleState(State):
        async def run(self):
            print(f"{self.agent.name}: In IDLE state")
            # Wait for an incoming message with job number and AMR number
            msg = await self.receive(timeout=float(inf))
            if msg:
                performative = msg.get_metadata("performative")
                if performative == "ask_machine" and msg.body=="canIcome":
                    self.agent.amr=msg.sender
                    reply = Message(to=msg.sender)
                    reply.set_metadata("performative", "machine_reply")
                    reply.body = "Yes"
                    await self.send(reply)
                    self.set_next_state(WAITING)
            else:
                print(f"{self.agent.name}: No message received, staying in IDLE state")
                self.set_next_state(IDLE)
                # The state machine will automatically go back to IDLE after the timeout
    
    class Waiting(State):
        async def run(self):
            print("waiting for amr")
            msg1 = await self.receive(timeout=float(inf))
            if msg1:
                performative = msg1.get_metadata("performative")
                if performative == "ask_machine" and msg1.body=="canIcome":
                    reply = Message(to=msg1.sender)
                    self.agent.dock_amr=msg1.sender
                    reply.set_metadata("performative", "machine_reply")
                    reply.body = "Come to Machine Dock"
                    await self.send(reply)
                    self.set_next_state(WAITING)
                elif performative == "waiting_for_machine_to_process":
                    machining_data=json.loads(msg1.body)
                    self.agent.currently_processed=machining_data[0]
                    self.agent.ptime=machining_data[1]
                    self.set_next_state(PROCESSING)




    class ProcessingState(State):
        async def run(self):
            print(f"{self.agent.name}: In PROCESSING state")
            print(f"{self.agent.name}: Currently processing: {self.agent.currently_processed}")
            
            # Simulate processing delay based on ptime
            await asyncio.sleep(self.agent.ptime)
            
            # After processing, send a "Processing complete" message back to the sender
            response = Message(to=self.agent.amr)
            response.set_metadata("performative", "machine_reply")
            response.body = "Processing complete"
            await self.send(response)
            
            print(f"{self.agent.name}: Sent 'Processing complete' to {self.agent.sender_jid}")
            
            # Transition back to IDLE state
            self.set_next_state(IDLE)
    
    async def setup(self):
        print(f"{self.name}: Agent starting...")

        # Initialize currently processed variable
        self.currently_processed = None
        self.sender_jid = None
        self.ptime = None
        self.amr=None
        
        # Initialize the state machine
        fsm = self.MachineBehaviour()
        fsm.add_state(name=IDLE, state=self.IdleState(), initial=True)
        fsm.add_state(name=WAITING, state=self.Waiting())
        fsm.add_state(name=PROCESSING, state=self.ProcessingState())
        
        fsm.add_transition(source=IDLE, dest=PROCESSING)
        fsm.add_transition(source=PROCESSING, dest=IDLE)
        fsm.add_transition(source=IDLE, dest=IDLE)


        # Add the FSM behavior to the agent
        self.add_behaviour(fsm)

async def main():
    # Create and start the agents
    machine1 = MachineAgent("machine1@jabber.fr", "changeme")
    await machine1.start()

    try:
        while machine1.is_alive():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await machine1.stop()

# Run the main function using asyncio
if __name__ == "__main__":
    asyncio.run(main())
