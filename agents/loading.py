
import json
from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message
import asyncio
from math import inf
import time
from collections import deque


# Define the states
INIT = "INIT"
IDLE = "IDLE"
LOADING = "LOADING"
# INFORM = "INFORM"


class LoadingDockAgent(Agent):
    class LoadingDockBehaviour(FSMBehaviour):
        async def on_start(self):
            print("LoadingDock FSM starting.")
        
        async def on_end(self):
            print("LoadingDock FSM finished.")
            await self.agent.stop()

    class InitState(State):
        async def run(self):
            print("INIT state: Waiting to receive job sets from scheduler")
            # Keep waiting until a message is received
            while self.agent.Init==True:
                msg = await self.receive(timeout=25)
                # await asyncio.sleep(5)  # Wait indefinitely for the job list
                if msg and msg.get_metadata("performative") == "Job_sets":
                    job_list = json.loads(msg.body)
                    self.agent.remaining_job_sets = deque(job_list)
                    # self.agent.max_amr=3#len(self.agent.remaining_job_sets)
                    print(f"Received job sets: {self.agent.remaining_job_sets}")
                    self.agent.Init=False
                    self.set_next_state(IDLE)
                else:
                    self.set_next_state(INIT)
                    print("No valid job sets received, retrying...")


    class IdleState(State):
        async def run(self):
            print("IDLE state: Listening for amr messages ")
            msg = await self.receive(timeout=30)
            if msg:
                # self.agent.sender_jid =self.agent.RAmrAgents[msg.sender.bare]
                if msg.get_metadata("performative") == "ask" and msg.body == "my_job_set" and self.agent.max_amr>self.agent.amr:
                    print(msg.sender,"requesting job set")
                    self.agent.num_amrs_registered += 1
                    job_set = self.agent.remaining_job_sets.popleft()
                    self.agent.assigned_job_sets = job_set
                    print(self.agent.amr)
                    call_msg = Message(to=str(msg.sender))
                    call_msg.set_metadata("performative", "loading_dock_ready")
                    call_msg.body = json.dumps(job_set)
                    await self.send(call_msg)
                    print("sent job set",job_set,"to",msg.sender)
                    self.agent.amr+=1
                    self.set_next_state(LOADING)

                elif msg.body == "load_the_job" and self.agent.max_amr>self.agent.amr:
                    print("Loading in Progress")
                    # Implement the job informing logic here
                    await asyncio.sleep(7)
                    loading_response = Message(to=str(msg.sender))
                    loading_response.set_metadata("performative", "loading")
                    loading_response.body = "loading_completed"
                    await self.send(loading_response)
                    self.set_next_state(IDLE) 

                elif msg.get_metadata("performative") == "ask" and msg.body == "my_job_set" and self.agent.max_amr<=self.agent.amr:
                    call_msg = Message(to=str(msg.sender))
                    call_msg.set_metadata("performative", "no jobs remaining")
                    call_msg.body = "wait for new job assignment"
                    await self.send(call_msg)
                    self.set_next_state(IDLE) 

                else:
                    print("Msg recived does not match")
                    self.set_next_state(IDLE)              

            else:
                print("No message received.")
                self.set_next_state(IDLE)

    class LoadingState(State):
        async def run(self):
            print("Loading state: Listening for amr messages ")
            msg = await self.receive(timeout=30)
            if msg:
                # self.agent.sender_jid =self.agent.RAmrAgents[msg.sender.bare]
                if msg.get_metadata("performative") == "ask" and msg.body == "load_the_job":
                    print("Loading in Progress")
                    # Implement the job informing logic here
                    await asyncio.sleep(7)
                    loading_response = Message(to=str(msg.sender))
                    loading_response.set_metadata("performative", "loading")
                    loading_response.body = "loading_completed"
                    await self.send(loading_response)
                    self.set_next_state(IDLE)

                else:
                    print("Msg recived does not match")
                    self.set_next_state(LOADING)  
                                 
            else:
                print("No message received.")
                self.set_next_state(LOADING)                



    # class InformState(State):
    #     async def run(self):
    #         print("INFORM state: Informing the agent about its job...")
    #         # Implement the job informing logic here
    #         await asyncio.sleep(3)
    #         loading_response = Message(to=self.agent.AmrAgents[self.agent.sender_jid])
    #         loading_response.set_metadata("performative", "loading")
    #         loading_response.body = "loading_completed"
    #         await self.send(loading_response)
    #         # After informing, transition back to IDLE state
    #         self.set_next_state(IDLE)

    async def setup(self):
        print("LoadingDock agent starting...")

        self.remaining_job_sets = None
        self.assigned_job_sets = None
        self.num_amrs_registered = 0
        self.sender_jid = None
        self.Init=True
        self.amr=0
        self.max_amr=6

        self.AmrAgents={
            '0':"robot1@jabber.fr",
            '1':"robot2@jabber.fr",
            '2':"robot3@jabber.fr",
            '3':"robot4@jabber.fr"
        }
        self.RAmrAgents={
            "robot1@jabber.fr":'0',
            "robot2@jabber.fr":'1',
            "robot3@jabber.fr":'2',
            "robot4@jabber.fr":'3'
        }

        fsm = self.LoadingDockBehaviour()

        fsm.add_state(name=INIT, state=self.InitState(), initial=True)
        fsm.add_state(name=IDLE, state=self.IdleState())
        fsm.add_state(name=LOADING, state=self.LoadingState())
        # fsm.add_state(name=INFORM, state=self.InformState())

        fsm.add_transition(source=INIT, dest=IDLE)
        fsm.add_transition(source=INIT, dest=INIT)
        fsm.add_transition(source=IDLE, dest=LOADING)
        fsm.add_transition(source=LOADING, dest=LOADING)
        fsm.add_transition(source=LOADING, dest=IDLE)
        # fsm.add_transition(source=IDLE, dest=INFORM)
        # fsm.add_transition(source=INFORM, dest=IDLE)
        fsm.add_transition(source=IDLE, dest=IDLE)
        fsm.add_transition(source=IDLE, dest=INIT)


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
