
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
UNLOADING = "UNLOADING"
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
                    print(f"Received job sets: {self.agent.remaining_job_sets}")
                    self.agent.Init=False
                    self.set_next_state(IDLE)
                else:
                    self.set_next_state(INIT)
                    print("No valid job sets received, retrying...")


    class IdleState(State):
        async def run(self):
            while self.agent.unloading_Q_dock==False:
                print("IDLE state: Listening for amr messages ")
                msg = await self.receive(timeout=30)
                if msg:
                    # self.agent.sender_jid =self.agent.RAmrAgents[msg.sender.bare]
                    if msg.get_metadata("performative") == "ask" and msg.body == "need to unload":
                        # Implement the job informing logic here
                        unloading_response = Message(to=str(msg.sender))
                        unloading_response.set_metadata("performative", "unload")
                        unloading_response.body = "come to unloading dock"
                        await self.send(unloading_response)
                        # print("Unloading completed")
                        self.set_next_state(UNLOADING)
                    else:
                        self.set_next_state(IDLE)
                else:
                    print("No message received.")
                    self.set_next_state(IDLE)

            while self.agent.unloading_Q_dock==True:
                unloading_response = Message(to=str(self.agent.Q_amr))
                unloading_response.set_metadata("performative", "unload")
                unloading_response.body = "come to unloading dock"
                await self.send(unloading_response)
                self.agent.unloading_Q_dock=False
                self.set_next_state(UNLOADING)



    class UnloadingState(State):
        async def run(self):
            print("UNLOADING state: Listening for amr messages ")
            msg = await self.receive(timeout=30)
            if msg:
                # self.agent.sender_jid =self.agent.RAmrAgents[msg.sender.bare]
                if msg.get_metadata("performative") == "ask" and msg.body == "need to unload":
                    unloading_response = Message(to=str(msg.sender))
                    unloading_response.set_metadata("performative", "unload")
                    unloading_response.body = "come to unloading Q dock"
                    await self.send(unloading_response)
                    self.agent.Q_amr=msg.sender.bare
                    self.agent.unloading_Q_dock=True
                    # print("Unloading completed")
                    self.set_next_state(UNLOADING)

                elif msg.get_metadata("performative") == "ask" and msg.body == "unload_the_job":
                    await asyncio.sleep(7)
                    unloading_response = Message(to=str(msg.sender))
                    unloading_response.set_metadata("performative", "unloading")
                    unloading_response.body = "unloading_completed"
                    await self.send(unloading_response)
                    # print("Unloading completed")
                    self.set_next_state(IDLE)
                else:
                     self.set_next_state(UNLOADING)
            else:
                 print("No message received.")
                 self.set_next_state(UNLOADING)                  



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

        self.Q_amr=None
        self.unloading_Q_dock=False

        self.AmrAgents={
            '0':"robot1@jabber.fr",
            '1':"robot2@jabber.fr",
            '2':"robot3@jabber.fr"
        }
        self.RAmrAgents={
            "robot1@jabber.fr":'0',
            "robot2@jabber.fr":'1',
            "robot3@jabber.fr":'2'
        }

        fsm = self.LoadingDockBehaviour()

        fsm.add_state(name=INIT, state=self.InitState())
        fsm.add_state(name=IDLE, state=self.IdleState(),initial=True)
        fsm.add_state(name=UNLOADING, state=self.UnloadingState())
        # fsm.add_state(name=INFORM, state=self.InformState())

        fsm.add_transition(source=INIT, dest=IDLE)
        fsm.add_transition(source=INIT, dest=INIT)
        fsm.add_transition(source=IDLE, dest=UNLOADING)
        # fsm.add_transition(source=IDLE, dest=INFORM)
        fsm.add_transition(source=UNLOADING, dest=IDLE)
        # fsm.add_transition(source=INFORM, dest=IDLE)
        fsm.add_transition(source=IDLE, dest=IDLE)
        fsm.add_transition(source=IDLE, dest=INIT)


        self.add_behaviour(fsm)

if __name__ == "__main__":
    loading_agent = LoadingDockAgent("unloadingdock@jabber.fr", "changeme")

    async def run():
        await loading_agent.start()
        print("Loading Agent started")

        try:
            while loading_agent.is_alive():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await loading_agent.stop()

    asyncio.run(run())
