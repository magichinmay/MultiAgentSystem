from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message
import asyncio
import json
from math import inf

# States
IDLE = "IDLE"
PROCESSING = "PROCESSING"

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
                try:
                    print(f"{self.agent.name}: Received job: {msg.body}")
                    job_amr_data = json.loads(msg.body)  # Ensure msg.body is valid JSON
                    job_number = job_amr_data[0]
                    ptime = job_amr_data[1]
                    
                    # Store the received job and AMR data in a variable
                    self.agent.currently_processed = (job_number, ptime)
                    
                    # Set the sender's jid to respond after processing
                    self.agent.sender_jid = str(msg.sender)
                    self.agent.ptime = ptime
                    
                    # Transition to the PROCESSING state
                    self.set_next_state(PROCESSING)
                except (json.JSONDecodeError, IndexError) as e:
                    print(f"{self.agent.name}: Error processing message: {e}")
                    # Optionally, you can log the error or take further action
            else:
                print(f"{self.agent.name}: No message received, staying in IDLE state")
                self.set_next_state(IDLE)
                # The state machine will automatically go back to IDLE after the timeout
    
    class ProcessingState(State):
        async def run(self):
            print(f"{self.agent.name}: In PROCESSING state")
            print(f"{self.agent.name}: Currently processing: {self.agent.currently_processed}")
            
            # Simulate processing delay based on ptime
            await asyncio.sleep(self.agent.ptime)
            
            # After processing, send a "Processing complete" message back to the sender
            response = Message(to=self.agent.sender_jid)
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
        
        # Initialize the state machine
        fsm = self.MachineBehaviour()
        fsm.add_state(name=IDLE, state=self.IdleState(), initial=True)
        fsm.add_state(name=PROCESSING, state=self.ProcessingState())
        
        fsm.add_transition(source=IDLE, dest=PROCESSING)
        fsm.add_transition(source=PROCESSING, dest=IDLE)
        fsm.add_transition(source=IDLE, dest=IDLE)


        # Add the FSM behavior to the agent
        self.add_behaviour(fsm)

async def main():
    # Create and start the agents
    machine1 = MachineAgent("machine1@jabber.fr", "changeme")
    machine2 = MachineAgent("machine2@jabber.fr", "changeme")
    
    await machine1.start()
    await machine2.start()

    try:
        while machine1.is_alive():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await machine1.stop()

    try:
        while machine2.is_alive():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await machine2.stop()


# Run the main function using asyncio
if __name__ == "__main__":
    asyncio.run(main())
