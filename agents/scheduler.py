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

class SchedulerAgent(Agent):
    def __init__(self, jid, password):
        super().__init__(jid, password)
        
        machine_data = benchmarks.pinedo['machine_data']
        ptime_data = benchmarks.pinedo['ptime_data']
        amrs = 2
        scheduler1 = JobShopScheduler(4, 3, amrs, 50, 0.7, 0.5, 100, machine_data, ptime_data)
        scheduler1.display_schedule = 0
        chromsome1 = scheduler1.GeneticAlgorithm()
    
        print("Machine Sequence", chromsome1.amr_machine_sequences)
        print("Ptime Sequence", chromsome1.amr_ptime_sequences)

        self.coordinates1 = chromsome1.amr_machine_sequences[0]  # Example list of coordinates
        self.ptime1=chromsome1.amr_ptime_sequences[0]
        print("AMR2 Machine sequence and it ptime", self.coordinates1,self.ptime1)
        
        self.coordinates2 = chromsome1.amr_machine_sequences[1]
        self.ptime2=chromsome1.amr_ptime_sequences[1]
        print("AMR3 Machine sequence and its ptime", self.coordinates2,self.ptime2)

        # Initialize state1 and state2
        self.state1 = "waiting for schedule"  # Added initialization for state1
        self.state2 = "waiting for schedule"  # Added initialization for state2
        
        self.index1 = 0  # Keep track of which coordinate to send
        self.index2 = 0 

    class AMRFSM(FSMBehaviour):
        async def on_start(self):
            print("Scheduler FSM started.")

        async def on_end(self):
            print("Scheduler FSM finished.")

    class SchedulerBehaviour(State):
        async def run(self):
            x=True
            while x==True:
                self.robots = []
                msg = await self.receive(timeout=15)
                if msg:
                    performative = msg.get_metadata("performative")
                    if performative == "Register":
                        self.robots.append(msg.body)
                        msg1 = Message(to=msg.body)
                        msg1.set_metadata("performative", "inform")
                        msg1.body = "Registered"
                        await self.send(msg1)
                        print(msg.body, "successfully registered")

                    elif performative == "robot2@jabber.fr" and msg.body == "Idle":
                        point1 = self.agent.coordinates1[self.agent.index1]  # Access agent's coordinates
                        time1 = self.agent.ptime1[self.agent.index1]
                        data1=[point1,time1]
                        msg = Message(to="robot2@jabber.fr")  # JID of the AMR2 agent
                        msg.set_metadata("performative", "order")
                        msg.body = json.dumps(data1)  # Convert the coordinate to JSON string
                        await self.send(msg)
                        print(f"Sending coordinate: {point1} to AMR2")
                        # Update index or mark completion
                        if self.agent.index1 < len(self.agent.coordinates1)-1:
                            self.agent.index1 += 1
                        else:
                            complete1 = Message(to="robot2@jabber.fr")
                            complete1.set_metadata("performative", "inform")
                            complete1.body = "AMR2 tasks are done"
                            self.agent.state1 = "Complete"
                            await self.send(complete1)
                            await asyncio.sleep(3)


                    elif performative == "robot3@jabber.fr" and msg.body == "Idle":
                        point2 = self.agent.coordinates2[self.agent.index2]  # Access agent's coordinates
                        time2 = self.agent.ptime2[self.agent.index2]
                        data2=[point2,time2]
                        msg = Message(to="robot3@jabber.fr")  # JID of the AMR3 agent
                        msg.set_metadata("performative", "order")
                        msg.body = json.dumps(data2)  # Convert the coordinate to JSON string
                        await self.send(msg) 
                        print(f"Sending coordinate: {point2} to AMR3")                
                        # Update index or mark completion
                        if self.agent.index2 < len(self.agent.coordinates2)-1:
                            self.agent.index2 += 1
                        else:
                            complete2 = Message(to="robot3@jabber.fr")
                            complete2.set_metadata("performative", "inform")
                            complete2.body = "AMR3 tasks are done"
                            self.agent.state2 = "Complete"
                            await self.send(complete2)
                            await asyncio.sleep(3)


                    # Check if both states are complete
                    if self.agent.state1 == "Complete" and self.agent.state2 == "Complete":
                        print("Both AMR tasks are complete.")
                        x=False
                        self.set_next_state("JobComplete")

                else:
                    print("No response from AMR, will retry after some time.")
                    await asyncio.sleep(5)

    class JobComplete(State):
        async def run(self):
            newjob = await self.receive(timeout=None)
            if newjob:
                performative = newjob.get_metadata("performative")
                if performative == "order" and newjob.body=="Jobs":
                    print(newjob.body)

    async def setup(self):
        fsm = self.AMRFSM()

        # All the States
        fsm.add_state(name="SchedulerBehaviour", state=self.SchedulerBehaviour(), initial=True)
        fsm.add_state(name="JobComplete", state=self.JobComplete())

        # Transition from one State to another State
        fsm.add_transition(source="SchedulerBehaviour", dest="JobComplete")
        fsm.add_transition(source="JobComplete", dest="SchedulerBehaviour")

        self.add_behaviour(fsm)

        # Register handlers for XMPP version and disco queries
        self.presence.version_handler = self.version_query_handler
        self.presence.disco_info_handler = self.disco_info_query_handler

    def version_query_handler(self, iq):
        iq.make_result()
        version_data = version.xso.Query()
        version_data.name = "SchedulerAgent"
        version_data.version = "1.0"
        iq.payload = version_data
        return iq

    def disco_info_query_handler(self, iq):
        iq.make_result()
        disco_data = disco.xso.InfoQuery()
        iq.payload = disco_data
        return iq


if __name__ == "__main__":
    scheduler_agent = SchedulerAgent("scheduler@jabber.fr", "changeme")

    async def run():
        await scheduler_agent.start()
        print("SchedulerAgent started")

        try:
            while scheduler_agent.is_alive():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await scheduler_agent.stop()

    asyncio.run(run())
