from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, FSMBehaviour, State
from spade.message import Message
import asyncio
import json
import sys
import os

from aioxmpp import version, disco


class MachineAgent(Agent):
    def __init__(self, jid, password):
        super().__init__(jid, password)
        print("Running Machine Agent 4")
        # Initialize state1 and state2
        self.state = "waiting for schedule"  # Added initialization for state1

        self.index = 0  # Keep track of which coordinate to send
        self.data=0
        self.x=True
        self.y=True

        self.waiting=True
        self.idle=True
        self.jobs=None
        self.Completed_Jobs=[]

    class AMRFSM(FSMBehaviour):
        async def on_start(self):
            print("Machine Agent 4 started.")

        async def on_end(self):
            print("Machine Agent 4 finished.")


    class waiting_for_op(State):
        async def run(self):
            print("waiting for jobs from scheduler")  
            while self.agent.waiting==True:  # Loop indefinitely until a message is received
                operation = await self.receive(timeout=25)  # Wait indefinitely
                if operation:
                    performative = operation.get_metadata("performative")
                    if performative == "jobs_from_scheduler":
                        self.agent.jobs = json.loads(operation.body)
                        print("The Jobs to be processed", self.agent.jobs)
                        self.agent.waiting=False
                        self.set_next_state("ProcessingState")
                        break  # Exit the loop when a job is received and processed
                else:
                    print("No message received, waiting...")


    class Idle(State):
        async def run(self):
            print("Changing state to Idle")
            while self.agent.idle==True:
                msg = await self.receive(timeout=25)
                if msg:
                    print(msg.body,"msg from",msg.sender)
                    performative = msg.get_metadata("performative")
                    if performative == "ask_machine_for_processing" and msg.body==str(self.agent.jobs[0][0]):
                        self.agent.amr=msg.sender
                        reply = Message(to=str(msg.sender))
                        reply.set_metadata("performative", "machine_reply")
                        reply.body = "Yes"
                        await self.send(reply)
                        self.agent.idle=False
                        self.set_next_state("ProcessingState")
                    else:
                        self.set_next_state("Idle")
                else:
                    print(f"{self.agent.name}: No message received, staying in IDLE state")
                    self.set_next_state("Idle")
                    # The state machine will automatically go back to IDLE after the timeout

    class ProcessingState(State):
        async def run(self):
            print("waiting for amr")
            msg=await self.receive(timeout=200)
            if msg:
                performative=msg.get_metadata("performative")
                if performative=="waiting_for_machine_to_process" and msg.body=="Ready":
                    machining=self.agent.jobs
                    job=machining[0][0]
                    operation=machining[0][1]
                    processing_time=machining[0][2]

                    print("Processing Job",job,"operation",operation)            
                    # Simulate processing delay based on ptime
                    await asyncio.sleep(processing_time)
                    completed_jobs=self.agent.jobs.pop(0)
                    self.agent.Completed_Jobs.append(completed_jobs)

                    # After processing, send a "Processing complete" message back to the sender
                    response = Message(to=str(msg.sender))
                    response.set_metadata("performative", "machine_reply")
                    response.body = "Processing complete"
                    await self.send(response)
                    self.agent.idle=True
                    print("Processing job",job,"completed")
                    # Transition back to IDLE state
                    self.set_next_state("ProcessingState")
                    print("Completed Jobs",self.agent.Completed_Jobs)
                    print("Remaining Jobs",self.agent.jobs)

                else:
                    self.set_next_state("ProcessingState")
            else:
                self.set_next_state("ProcessingState")



    async def setup(self):
        fsm = self.AMRFSM()

        # All the States
        fsm.add_state(name="waiting_for_op", state=self.waiting_for_op(), initial=True)
        fsm.add_state(name="Idle", state=self.Idle())
        fsm.add_state(name="ProcessingState", state=self.ProcessingState())

        # Transition from one State to another State
        fsm.add_transition(source="waiting_for_op", dest="waiting_for_op")
        fsm.add_transition(source="waiting_for_op", dest="Idle")

        fsm.add_transition(source="Idle", dest="Idle")
        fsm.add_transition(source="Idle", dest="ProcessingState")

        fsm.add_transition(source="waiting_for_op", dest="ProcessingState")
        fsm.add_transition(source="ProcessingState", dest="waiting_for_op")

        fsm.add_transition(source="ProcessingState", dest="ProcessingState")
        fsm.add_transition(source="ProcessingState", dest="Idle")

        self.add_behaviour(fsm)

        # Register handlers for XMPP version and disco queries
        self.presence.version_handler = self.version_query_handler
        self.presence.disco_info_handler = self.disco_info_query_handler

    def version_query_handler(self, iq):
        iq.make_result()
        version_data = version.xso.Query()
        version_data.name = "MachineAgent"
        version_data.version = "1.0"
        iq.payload = version_data
        return iq

    def disco_info_query_handler(self, iq):
        iq.make_result()
        disco_data = disco.xso.InfoQuery()
        iq.payload = disco_data
        return iq


if __name__ == "__main__":
    scheduler_agent = MachineAgent("machine4@jabber.fr", "changeme")

    async def run():
        await scheduler_agent.start()
        print("MachineAgent started")

        try:
            while scheduler_agent.is_alive():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await scheduler_agent.stop()

    asyncio.run(run())