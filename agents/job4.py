from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, FSMBehaviour, State
from spade.message import Message
import asyncio
import json
import sys
import os

from aioxmpp import version, disco


class JobAgent4(Agent):
    def __init__(self, jid, password):
        super().__init__(jid, password)
        print("Running Job Agent 1")
        # Initialize state1 and state2
        self.state = "waiting for schedule"  # Added initialization for state1

        self.index = 0  # Keep track of which coordinate to send
        self.data=0
        self.x=True
        self.y=True
        self.amr=None
        self.operations=[]

    class AMRFSM(FSMBehaviour):
        async def on_start(self):
            print("Scheduler FSM started.")

        async def on_end(self):
            print("Scheduler FSM finished.")

    class waitingforjob(State):
        async def run(self):
            print("waiting for jobs")  
            while self.agent.x==True:
                self.robots = []
                msg = await self.receive(timeout=15)
                if msg:
                    performative = msg.get_metadata("performative")
                    if performative == "say" and msg.body=="status":
                        print("sending job agent status")
                        say=Message(to="scheduler@jabber.fr")
                        say.set_metadata("performative","say")
                        say.body="waitingforjob"
                        await self.send(say)

                    if performative == "inform":
                        try:
                            self.agent.data = json.loads(msg.body)
                            if isinstance(self.agent.data, list):
                                print(f"Received Operations: {self.agent.data}")
                                self.agent.x=False
                                for i in (self.agent.data):
                                    if i[1]!=0:
                                        self.agent.operations.append(i)
                                self.set_next_state("sendingcoordinates")
                            else:
                                print("Error: Received data is not a valid coordinate.")
                                self.set_next_state("waitingforjob")
                        except json.JSONDecodeError:
                            print("Error: Unable to decode message body as JSON.")
                            self.set_next_state("waitingforjob")
                else:
                    print("No response from AMR, will retry after some time.")
                    await asyncio.sleep(5)

    class sendingcoordinates(State):
        async def run(self):
            print("Changing state to sendingcoordinates")
            
            job = await self.receive(timeout=250)
            if job:
                performative = job.get_metadata("performative")
                if performative == "ask_for_op" and job.body=="Idle":
                    print("Received request from",job.sender)
                    msg=Message(to=str(job.sender))
                    msg.set_metadata("performative","job_orders")
                    coordinates=self.agent.operations[self.agent.index]
                    msg.body = json.dumps(coordinates)
                    await self.send(msg)
                    print(f"Sending coordinate: {coordinates} to AMR")

                    if self.agent.index < len(self.agent.operations)-1:
                        self.agent.index += 1
                        self.set_next_state("sendingcoordinates")
                    else:
                        self.agent.amr=job.sender.bare
                        # complete1 = Message(to=str(job.sender))
                        # complete1.set_metadata("performative", "inform_amr")
                        # complete1.body = "tasks are done"
                        # self.agent.state = "Complete"
                        # await self.send(complete1)
                        self.set_next_state("JobComplete") 

                else:
                    self.set_next_state("sendingcoordinates")
            else:
                self.set_next_state("sendingcoordinates")

            # # Check if both states are complete
            # if self.agent.state == "Complete" :
            #     self.agent.y=False
                

    class JobComplete(State):
        async def run(self):
            print("All the operations completed")
            job = await self.receive(timeout=20)
            if job:
                performative = job.get_metadata("performative")
                if performative == "ask_for_op" and job.body=="Idle":
                    print('sent task completed msg to',job.sender)
                    complete1 = Message(to=str(job.sender))
                    complete1.set_metadata("performative", "inform_amr")
                    complete1.body = "tasks are done"
                    self.agent.state = "Complete"
                    await self.send(complete1)
                else:
                    self.set_next_state("JobComplete") 
            else:
                self.set_next_state("JobComplete") 

            # newjob = await self.receive(timeout=None)
            # if newjob:
            #     performative = newjob.get_metadata("performative")
            #     if performative == "order" and newjob.body=="newjob":
            #         self.set_next_state("waitingforjob")

    async def setup(self):
        fsm = self.AMRFSM()

        # All the States
        fsm.add_state(name="waitingforjob", state=self.waitingforjob(), initial=True)
        fsm.add_state(name="sendingcoordinates", state=self.sendingcoordinates())
        fsm.add_state(name="JobComplete", state=self.JobComplete())

        # Transition from one State to another State
        fsm.add_transition(source="waitingforjob", dest="sendingcoordinates")
        fsm.add_transition(source="sendingcoordinates", dest="waitingforjob")
        fsm.add_transition(source="sendingcoordinates", dest="sendingcoordinates")
        fsm.add_transition(source="sendingcoordinates", dest="JobComplete")
        fsm.add_transition(source="JobComplete", dest="waitingforjob")
        fsm.add_transition(source="JobComplete", dest="JobComplete")

        self.add_behaviour(fsm)

        # Register handlers for XMPP version and disco queries
        self.presence.version_handler = self.version_query_handler
        self.presence.disco_info_handler = self.disco_info_query_handler

    def version_query_handler(self, iq):
        iq.make_result()
        version_data = version.xso.Query()
        version_data.name = "JobAgent4"
        version_data.version = "1.0"
        iq.payload = version_data
        return iq

    def disco_info_query_handler(self, iq):
        iq.make_result()
        disco_data = disco.xso.InfoQuery()
        iq.payload = disco_data
        return iq


if __name__ == "__main__":
    scheduler_agent = JobAgent4("job4@jabber.fr", "changeme")

    async def run():
        await scheduler_agent.start()
        # scheduler_agent.web.start(hostname="127.0.0.1", port="100010")
        print("JobAgent4 started")

        try:
            while scheduler_agent.is_alive():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await scheduler_agent.stop()

    asyncio.run(run())