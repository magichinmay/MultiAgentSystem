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
        self.amrs = 3
        amrs=self.amrs
        self.jobs=3
        jobs=self.jobs
        machines=4
        scheduler1 = JobShopScheduler(machines, jobs, amrs, 50, 0.7, 0.5, 100, machine_data, ptime_data)
        scheduler1.display_schedule = 0
        chromsome1 = scheduler1.GeneticAlgorithm()
        self.operation_list=scheduler1.operation_data

        amr1=chromsome1.amr_list[0]
        amr2=chromsome1.amr_list[1]
        amr3=chromsome1.amr_list[2]
        self.amr_jobs=[amr1.completed_jobs,amr2.completed_jobs,amr3.completed_jobs]

        print("amr1",amr1.completed_jobs)
        print("amr2",amr2.completed_jobs)
        print("amr3",amr3.completed_jobs)
        print("amr",self.amr_jobs)
        print("Machine Sequence", self.operation_list)
        print("Machine Sequence", self.operation_list[0])

        # Initialize state1 and state2
        self.state1 = "waiting for schedule"  # Added initialization for state1
        self.state2 = "waiting for schedule"  # Added initialization for state2
        
        self.index1 = 0  # Keep track of which coordinate to send
        self.index2 = 0 
        self.robots = []
        self.JobAgents=["job1@jabber.fr","job2@jabber.fr","job3@jabber.fr"]

    class AMRFSM(FSMBehaviour):
        async def on_start(self):
            print("Scheduler FSM started.")

        async def on_end(self):
            print("Scheduler FSM finished.")

    class SchedulerBehaviour(State):
        async def run(self):
            for index,element in enumerate(self.agent.JobAgents):
                await asyncio.sleep(5)
                msg=Message(to=element)
                print(element)
                msg.set_metadata("performative","say")
                msg.body="status"
                await self.send(msg)
                print("waiting for Job Agent response")
                await asyncio.sleep(2)

                msg1 = await self.receive(timeout=15)
                if msg1:
                    performative=msg1.get_metadata("performative")
                    if performative=="say" and msg1.body=="waitingforjob":
                        operation_and_ptime=self.agent.operation_list[index]
                        msg=Message(to=element)
                        msg.set_metadata("performative","inform")
                        msg.body = json.dumps(operation_and_ptime)
                        await self.send(msg)
            await asyncio.sleep(2)
            print("Changing state to RobotRegister")
            self.set_next_state("RobotRegister")

    class RobotRegister(State):
        async def run(self):
            x=True         
            while x==True:
                msg = await self.receive(timeout=None)
                if msg:
                    performative = msg.get_metadata("performative")
                    if performative == "Register":
                        self.agent.robots.append(msg.body)
                        msg1 = Message(to=msg.body)
                        msg1.set_metadata("performative", "inform")
                        msg1.body = "Registered"
                        await self.send(msg1)
                        print(msg.body, "successfully registered")
                        if len(self.agent.robots)>=self.agent.amrs:
                            x=False
                else:
                    print("No response from AMR, will retry after some time.")
                    await asyncio.sleep(5)

            robots1=self.agent.robots
            i=0
            while self.agent.amrs>=i:
                msg1=await self.receive(timeout=None)
                if msg1:
                    performative = msg1.get_metadata("performative")
                    if performative == "ask" and msg1.body=="my job":
                        msg=Message(to=msg1.sender)
                        print(msg1.sender)
                        msg.set_metadata("performative", "order")
                        msg.body = json.dumps(self.agent.amr_jobs[i])
                        i+=1
                        print(msg.body)
                        await self.send(msg)
                        print("sent jobs to",msg1.sender)
                        await asyncio.sleep(3)
            self.set_next_state("JobComplete")

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
        fsm.add_state(name="RobotRegister", state=self.RobotRegister())
        fsm.add_state(name="JobComplete", state=self.JobComplete())

        # Transition from one State to another State
        fsm.add_transition(source="SchedulerBehaviour", dest="JobComplete")
        fsm.add_transition(source="SchedulerBehaviour", dest="RobotRegister")
        fsm.add_transition(source="RobotRegister", dest="SchedulerBehaviour")
        fsm.add_transition(source="RobotRegister", dest="JobComplete")
        fsm.add_transition(source="JobComplete", dest="SchedulerBehaviour")
        fsm.add_transition(source="JobComplete", dest="RobotRegister")

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
