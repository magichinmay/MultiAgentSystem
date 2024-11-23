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
        # self.JobAgents=["job1@jabber.fr","job2@jabber.fr","job3@jabber.fr","job4@jabber.fr","job5@jabber.fr"]
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
        self.new_jobs=0
        self.amr_location=[]
        

    class AMRFSM(FSMBehaviour):
        async def on_start(self):
            print("Scheduler FSM started.")

        async def on_end(self):
            print("Scheduler FSM finished.")

    class RobotRegister(State):
        async def run(self):
            start_time_schedule = time.time()  # Record the start time
            start_time_reschedule = time.time()  # Record the start time
            timeout_duration = 48  # Total time to keep the scheduler open

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
            registered_amr=len(self.agent.amrs)
            print("No of registerd amrs",registered_amr)
            max_amr=3
            if registered_amr<=max_amr:
                amr=registered_amr
            else:
                amr=max_amr
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
            machine_data = benchmarks.custom_sim['machine_data']
            ptime_data = benchmarks.custom_sim['ptime_data']
            amr=len(self.agent.amrs)
            jobs=5
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

            # unload=Message

            #Sends all the Job's opeartion detail to each Machine Agent
            for index,machines in enumerate(self.agent.Machine):
                Machine_Job_Set=self.agent.machine_job_set[index]
                Mmsg2=Message(to=machines)
                Mmsg2.set_metadata("performative","jobs_from_scheduler")
                Mmsg2.body=json.dumps(Machine_Job_Set)
                await self.send(Mmsg2)
                print("sent job data to machine to",index)
                await asyncio.sleep(4)


            # print("Changing state to RobotRegister")
            self.agent.open_for_reschedule=True
            self.set_next_state("JobProcessing")

    class JobProcessing(State):
        async def run(self):
            amr1_reply= await self.receive(timeout=30)
            if amr1_reply:
                if amr1_reply.get_metadata("performative") == "Breakdown: please assist" :
                    self.agent.amr_location = json.loads(amr1_reply.body)

                    Mmsg2=Message(to=str(amr1_reply.sender))
                    Mmsg2.set_metadata("performative","ask")
                    Mmsg2.body="send jobs yet to processed"
                    await self.send(Mmsg2)

                    amr2_reply= await self.receive(timeout=40)
                    if amr2_reply:
                        if amr2_reply.get_metadata("performative") == "jobs" :
                            self.agent.new_jobs = json.loads(amr2_reply.body)
                            self.set_next_state("check_amr")

                # elif amr1_reply.get_metadata("performative") == "Breakdown: please assist" and amr1_reply.body=="":
                else:
                    self.set_next_state("JobProcessing")
            else:
                self.set_next_state("JobProcessing")

    class check_amr(State):
        async def run(self):
            for amr in self.agent.amrs:
                Mmsg2=Message(to=str(amr))
                Mmsg2.set_metadata("performative","ask")
                Mmsg2.body="available"
                await self.send(Mmsg2)
                ask1=await self.receive(timeout=30)
                if ask1:
                    if ask1.get_metadata("performative") == "tell" and ask1.body=="yes" :
                        self.agent.available_amr=ask1.sender
                        self.set_next_state("send_breakdown_msg")
                        break  
                              


    class send_breakdown_msg(State):
        async def run(self):
            Mmsg2=Message(to=str(self.agent.available_amr))
            Mmsg2.set_metadata("performative","new jobs")
            Mmsg2.body=json.dumps(self.agent.amr_location)
            await self.send(Mmsg2)
            ask1=await self.receive(timeout=30)
            if ask1:
                if ask1.get_metadata("performative") == "ask" and ask1.body=="send jobs" :
                    ask=Message(to=str(ask1.sender))
                    ask.set_metadata("performative", "jobs")
                    ask.body = json.loads(self.agent.new_jobs)
                    print(ask.body)
                    await self.send(ask)
                    self.set_next_state("JobProcessing")
                                    


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
        fsm.add_state(name="JobProcessing", state=self.JobProcessing())
        fsm.add_state(name="check_amr", state=self.check_amr())
        fsm.add_state(name="send_breakdown_msg", state=self.send_breakdown_msg())
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
        fsm.add_transition(source="Send_Schedule", dest="JobProcessing")
        fsm.add_transition(source="JobProcessing", dest="JobComplete")
        fsm.add_transition(source="JobProcessing", dest="JobProcessing")
        fsm.add_transition(source="JobProcessing", dest="check_amr")
        fsm.add_transition(source="check_amr", dest="send_breakdown_msg")
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
        # scheduler_agent.web.start(hostname="127.0.0.1", port="10000")

        try:
            while scheduler_agent.is_alive():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await scheduler_agent.stop()

    asyncio.run(run())
