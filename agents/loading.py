
import json
from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message
import asyncio
from math import inf
from collections import deque

# Define the states
INIT = "INIT"
IDLE = "IDLE"
LOADING = "LOADING"
INFORM = "INFORM"

class LoadingDockAgent(Agent):
    class LoadingDockBehaviour(FSMBehaviour):
        async def on_start(self):
            print("LoadingDock FSM starting.")
        
        async def on_end(self):
            print("LoadingDock FSM finished.")
            await self.agent.stop()

    class InitState(State):
        async def run(self):
            print("INIT state: Receiving job sets...")
            msg = await self.receive(timeout=10)  # Wait for the job list
            if msg:
                if msg.get_metadata("performative") == "Job_sets":
                    job_list = json.loads(msg.body)
                    self.agent.remaining_job_sets = deque(job_list)
                    print(f"Received job sets: {self.agent.remaining_job_sets}")
                    self.set_next_state(IDLE)
            else:
                print("No job sets received.")
                self.set_next_state(INIT)

    class IdleState(State):
        async def run(self):
            print("IDLE state: Listening for messages...")
            msg = await self.receive(timeout=10)
            if msg:
                self.agent.sender_jid = msg.sender
                if msg.get_metadata("performative") == "ask":
                    if msg.body == "my_job_set":
                        self.set_next_state(LOADING)
                    elif msg.body == "load_the_job":
                        self.set_next_state(INFORM)
            else:
                print("No message received.")
                self.set_next_state(IDLE)

    class LoadingState(State):
        async def run(self):
            print("LOADING state: Loading jobs...\n  with job sets: ", self.agent.remaining_job_sets)
            # Implement the job loading logic here
            # After loading, transition back to IDLE state
            self.agent.num_amrs_registered += 1
            job_set = self.agent.remaining_job_sets.popleft()
            self.agent.assigned_job_sets = job_set
            call_msg = Message(to=str(self.agent.sender_jid))
            call_msg.set_metadata("performative", "loading_dock_ready")
            call_msg.body = json.dumps(job_set)
            await self.send(call_msg)
            self.set_next_state(IDLE)

    class InformState(State):
        async def run(self):
            print("INFORM state: Informing the agent about its job...")
            # Implement the job informing logic here
            await asyncio.sleep(3)
            loading_response = Message(to=str(self.agent.sender_jid))
            loading_response.set_metadata("performative", "loading")
            loading_response.body = "loading_completed"
            await self.send(loading_response)
            # After informing, transition back to IDLE state
            self.set_next_state(IDLE)

    async def setup(self):
        print("LoadingDock agent starting...")

        self.remaining_job_sets = None
        self.assigned_job_sets = None
        self.num_amrs_registered = 0
        self.sender_jid = None

        fsm = self.LoadingDockBehaviour()

        fsm.add_state(name=INIT, state=self.InitState(), initial=True)
        fsm.add_state(name=IDLE, state=self.IdleState())
        fsm.add_state(name=LOADING, state=self.LoadingState())
        fsm.add_state(name=INFORM, state=self.InformState())

        fsm.add_transition(source=INIT, dest=IDLE)
        fsm.add_transition(source=INIT, dest=INIT)
        fsm.add_transition(source=IDLE, dest=LOADING)
        fsm.add_transition(source=IDLE, dest=INFORM)
        fsm.add_transition(source=LOADING, dest=IDLE)
        fsm.add_transition(source=INFORM, dest=IDLE)
        fsm.add_transition(source=IDLE, dest=IDLE)


        self.add_behaviour(fsm)

if __name__ == "__main__":
    loading_agent = LoadingDockAgent("loadingdock@jabber.fr", "changeme")

    async def run():
        await loading_agent.start()
        print("Loading Agent started")

        try:
            while loading_agent.is_alive():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await loading_agent.stop()

    asyncio.run(run())
