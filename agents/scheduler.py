from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, FSMBehaviour, State
from spade.message import Message
import asyncio
import json
import sys
import os
import time

from aioxmpp import version, disco

current_dir = os.path.dirname(os.path.abspath(__file__))

# Construct the path to the JobShopGA_withAMR directory
jobshop_ga_dir = os.path.join(current_dir, '..', 'JobShopGA_withAMR')

# Add this directory to sys.path
sys.path.insert(0, jobshop_ga_dir)

# Now you can import from the JobShopGA_withAMR directory
from JobShopScheduler import JobShopScheduler
import benchmarks
import distances

class SchedulerAgent(Agent):
    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.amrs = []
        self.JobAgents=["job1@jabber.fr","job2@jabber.fr","job3@jabber.fr"]
        self.Machine=["machine1@jabber.fr","machine2@jabber.fr","machine3@jabber.fr","machine4@jabber.fr"]
        self.job_sets = []
        self.operation_data=[]
        self.machine_job_set = []
        self.open_for_reschedule=False
        self.scmax=0
        self.rcmax=0
        self.r=False
        self.job_sequences_for_machines = []
        

    class AMRFSM(FSMBehaviour):
        async def on_start(self):
            print("Scheduler FSM started.")

        async def on_end(self):
            print("Scheduler FSM finished.")

    class RobotRegister(State):
        async def run(self):
            start_time_schedule = time.time()  # Record the start time
            start_time_reschedule = time.time()  # Record the start time
            timeout_duration = 24  # Total time to keep the scheduler open

            if self.agent.open_for_reschedule==False:
                print("Scheduler open for Registration")
                while time.time() - start_time_schedule < timeout_duration:
                    msg = await self.receive(timeout=12)
                    if msg:
                        performative = msg.get_metadata("performative")
                        if performative == "Register":
                            self.agent.amrs.append(msg.body)  # Append AMR ID to the list
                            msg1 = Message(to=msg.body)
                            msg1.set_metadata("performative", "inform")
                            msg1.body = "Registered"
                            await self.send(msg1)
                            print(msg.body, "Successfully Registered")
                    else:
                        print("No Registration Request")
                        await asyncio.sleep(5)
                # Set next state after 60 seconds
                self.set_next_state("Scheduler")
                

            if self.agent.open_for_reschedule==True:
                print("Scheduler open for Re-registration")
                while time.time() - start_time_reschedule < (self.agent.scmax-10):
                    msg = await self.receive(timeout=12)
                    if msg:
                        self.agent.r=True
                        performative = msg.get_metadata("performative")
                        if performative == "Register":
                            self.agent.amrs.append(msg.body)  # Append AMR ID to the list
                            msg1 = Message(to=msg.body)
                            msg1.set_metadata("performative", "inform")
                            msg1.body = "Registered"
                            await self.send(msg1)
                            print(msg.body, "Successfully Registered")
                        elif performative == "Breakdown: please assist":
                            self.agent.amrs.remove(msg.body)
                    else:
                        print("No Registration Request")
                        await asyncio.sleep(5)

                if self.agent.r==True:        
                    # Set next state after 60 seconds
                    self.set_next_state("Reschedule")
            


    class Scheduler(State):
        async def run(self):
            machine_data = benchmarks.pinedo['machine_data']
            ptime_data = benchmarks.pinedo['ptime_data']
            amr=len(self.agent.amrs)
            print("No of amrs",amr)
            jobs=3
            machines=4
            scheduler1 = JobShopScheduler(machines, jobs, amr, 50, 0.7, 0.5, 100, machine_data, ptime_data)
            scheduler1.display_schedule = 0
            chromsome1 = scheduler1.GeneticAlgorithm()
            self.agent.operation_data=scheduler1.operation_data
            
            amr_list=chromsome1.amr_list
            for amrs in amr_list:
                self.agent.job_sets.append(amrs.completed_jobs)
            print(self.agent.job_sets)

            machine_list = chromsome1.machine_list
            for machine in machine_list:              
                machine_sublist = []
                for operation in machine.operationlist:
                    if operation.Pj!=0:                        
                        machine_sublist.append([operation.job_number, operation.operation_number, operation.Pj])
                
                self.agent.machine_job_set.append(machine_sublist)
            
            self.agent.scmax=chromsome1.Cmax
            print("machine_job_set",self.agent.machine_job_set)
            print("job sequences for machines",self.agent.job_sequences_for_machines)
            self.set_next_state("Send_Schedule")



    class Reschedule(State):
        async def run(self):
            machine_data = benchmarks.pinedo['machine_data']
            ptime_data = benchmarks.pinedo['ptime_data']
            amr=len(self.agent.amrs)
            jobs=3
            machines=4
            scheduler1 = JobShopScheduler(machines, jobs, amr, 50, 0.7, 0.5, 100, machine_data, ptime_data)
            scheduler1.display_schedule = 0
            chromsome1 = scheduler1.GeneticAlgorithm()
            self.agent.operation_list=scheduler1.operation_data
            
            amr_list=chromsome1.amr_list
            job_sets = []
            for amr in amr_list:
                job_sets.append(amr.completed_jobs)

            print("machine_job_set",self.agent.machine_job_set)
            self.set_next_state("Send_Schedule")




    class Send_Schedule(State):
        async def run(self):
            #Sends Job Operations to Job Agents
            for index,element in enumerate(self.agent.JobAgents):
                Jmsg=Message(to=element)
                print(element)
                Jmsg.set_metadata("performative","say")
                Jmsg.body="status"
                await self.send(Jmsg)
                print("waiting for Job Agent response")
                await asyncio.sleep(2)
                Jmsg1 = await self.receive(timeout=20)
                if Jmsg1:
                    performative=Jmsg1.get_metadata("performative")
                    if performative=="say" and Jmsg1.body=="waitingforjob":
                        operation_and_ptime=self.agent.operation_data[index]
                        Jmsg2=Message(to=element)
                        Jmsg2.set_metadata("performative","inform")
                        Jmsg2.body = json.dumps(operation_and_ptime)
                        await self.send(Jmsg2)
            await asyncio.sleep(4)


            Lmsg2=Message(to="loadingdock@jabber.fr")
            Lmsg2.set_metadata("performative","Job_sets")
            Lmsg2.body=json.dumps(self.agent.job_sets)
            print(self.agent.job_sets)
            await self.send(Lmsg2)
            await asyncio.sleep(4)

            unload=Message

            #Sends all the Job's opeartion detail to each Machine Agent
            for index,machines in enumerate(self.agent.Machine):
                Machine_Job_Set=self.agent.machine_job_set[index]
                Mmsg2=Message(to=machines)
                Mmsg2.set_metadata("performative","jobs_from_scheduler")
                Mmsg2.body=json.dumps(Machine_Job_Set)
                await self.send(Mmsg2)
                print("sent job data to machine to",index)
                await asyncio.sleep(4)


            print("Changing state to RobotRegister")
            self.agent.open_for_reschedule=True
            self.set_next_state("JobComplete")



    class JobComplete(State):
        async def run(self):
            print("All Jobs complete")
            await asyncio.sleep(25)
            self.set_next_state("JobComplete")
            # newjob = await self.receive(timeout=None)
            # if newjob:
            #     performative = newjob.get_metadata("performative")
            #     if performative == "new_schedule" and newjob.body=="Reschedule":
            #         print(newjob.body)

            #         self.set_next_state("Reschedule")

    async def setup(self):
        fsm = self.AMRFSM()

        # All the States
        fsm.add_state(name="RobotRegister", state=self.RobotRegister(), initial=True)
        fsm.add_state(name="Scheduler", state=self.Scheduler())
        fsm.add_state(name="Reschedule", state=self.Reschedule())
        fsm.add_state(name="Send_Schedule", state=self.Send_Schedule())
        fsm.add_state(name="JobComplete", state=self.JobComplete())

        # Transition from one State to another State
        fsm.add_transition(source="RobotRegister", dest="Scheduler")
        fsm.add_transition(source="Scheduler", dest="RobotRegister")
        
        fsm.add_transition(source="Reschedule", dest="RobotRegister")
        fsm.add_transition(source="RobotRegister", dest="Reschedule")

        fsm.add_transition(source="Scheduler", dest="Send_Schedule")
        fsm.add_transition(source="Reschedule", dest="Send_Schedule")

        fsm.add_transition(source="Send_Schedule", dest="Send_Schedule")
        fsm.add_transition(source="Send_Schedule", dest="RobotRegister")
        fsm.add_transition(source="Send_Schedule", dest="Reschedule")
        fsm.add_transition(source="Send_Schedule", dest="JobComplete")
        fsm.add_transition(source="JobComplete", dest="JobComplete")

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
        scheduler_agent.web.start(hostname="127.0.0.1", port="10000")

        try:
            while scheduler_agent.is_alive():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await scheduler_agent.stop()

    asyncio.run(run())
