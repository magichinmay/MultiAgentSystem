from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, FSMBehaviour, State
from spade.message import Message
import asyncio
import json
import sys
import os

from aioxmpp import version, disco

sys.path.insert(1, "/home/ubantu/mas_ws/src/MultiAgentSystem/JobShopGA")
from JobShopScheduler import JobShopScheduler
import benchmarks
import distances

class JobAgent2(Agent):
    def __init__(self, jid, password):
        super().__init__(jid, password)
        print("Running Job Agent 2")
        # Initialize state1 and state2
        self.state = "waiting for schedule"  # Added initialization for state1

        self.index = 0  # Keep track of which coordinate to send
        self.data=0

    class AMRFSM(FSMBehaviour):
        async def on_start(self):
            print("Scheduler FSM started.")

        async def on_end(self):
            print("Scheduler FSM finished.")

    class waitingforjob(State):
        async def run(self):
            print("waiting for jobs")
            x=True
            while x==True:
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
            y=True
            while y==True:
                job = await self.receive(timeout=None)
                if job:
                    performative = job.get_metadata("performative")
                    if performative == "request" and job.body=="Idle":
                        msg=Message(to=job.sender)
                        msg.set_metadata("performative","order")
                        coordinates=self.agent.data[self.agent.index]
                        msg.body = json.dumps(coordinates)
                        await self.send(msg)
                        print(f"Sending coordinate: {coordinates} to AMR1")
                    # Update index or mark completion
                    if self.agent.index < len(self.agent.data)-1:
                        self.agent.index += 1
                    else:
                        complete1 = Message(to="robot1@jabber.fr")
                        complete1.set_metadata("performative", "inform")
                        complete1.body = "AMR1 tasks are done"
                        self.agent.state = "Complete"
                        await self.send(complete1)
                        await asyncio.sleep(3)

                # Check if both states are complete
                if self.agent.state == "Complete" :
                    print("Both AMR tasks are complete.")
                    y=False
                    self.set_next_state("JobComplete")

    class JobComplete(State):
        async def run(self):
            newjob = await self.receive(timeout=None)
            if newjob:
                performative = newjob.get_metadata("performative")
                if performative == "order" and newjob.body=="newjob":
                    self.set_next_state("waitingforjob")

    async def setup(self):
        fsm = self.AMRFSM()

        # All the States
        fsm.add_state(name="waitingforjob", state=self.waitingforjob(), initial=True)
        fsm.add_state(name="sendingcoordinates", state=self.sendingcoordinates())
        fsm.add_state(name="JobComplete", state=self.JobComplete())

        # Transition from one State to another State
        fsm.add_transition(source="waitingforjob", dest="sendingcoordinates")
        fsm.add_transition(source="sendingcoordinates", dest="waitingforjob")
        fsm.add_transition(source="sendingcoordinates", dest="JobComplete")
        fsm.add_transition(source="JobComplete", dest="waitingforjob")

        self.add_behaviour(fsm)

        # Register handlers for XMPP version and disco queries
        self.presence.version_handler = self.version_query_handler
        self.presence.disco_info_handler = self.disco_info_query_handler

    def version_query_handler(self, iq):
        iq.make_result()
        version_data = version.xso.Query()
        version_data.name = "JobAgent2"
        version_data.version = "1.0"
        iq.payload = version_data
        return iq

    def disco_info_query_handler(self, iq):
        iq.make_result()
        disco_data = disco.xso.InfoQuery()
        iq.payload = disco_data
        return iq


if __name__ == "__main__":
    scheduler_agent = JobAgent2("job2@jabber.fr", "changeme")

    async def run():
        await scheduler_agent.start()
        print("JobAgent2 started")

        try:
            while scheduler_agent.is_alive():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await scheduler_agent.stop()

    asyncio.run(run())