from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message
import asyncio
import json
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from aioxmpp import version, disco
from geometry_msgs.msg import PoseStamped
from rclpy.duration import Duration
import rclpy
from collections import deque
import time

if not rclpy.ok():  # Ensure rclpy.init() is called only once
    rclpy.init()

class AMR1(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.remainingjobs=deque()
        self.completed_jobs = []
        self.JobsAgents={
            '0':"job1@jabber.fr",
            '1':"job2@jabber.fr",
            '2':"job3@jabber.fr"
        }
        self.RRJobAgents={
            "job1@jabber.fr":'0',
            "job2@jabber.fr":'1',
            "job3@jabber.fr":'2'
        }
        self.MachineAgents={
            '0':"machine1@jabber.fr",
            '1':"machine2@jabber.fr",
            '2':"machine3@jabber.fr",
            '3':"machine4@jabber.fr"
        }
        self.RMachineAgents={
            "machine1@jabber.fr":'0',
            "machine2@jabber.fr":'1',
            "machine3@jabber.fr":'2',
            "machine4@jabber.fr":'3'
        }
        self.Workstations = {
                '0': 'machine1',
                '1': 'machine2',
                '2': 'machine3',
                '3': 'machine4',
                '-1': 'loading_dock',
                '-2': 'unloading_dock'
            }
        self.waiting_for_job=True
        self.going_to_loading=True
        self.going_to_unloading=True
        self.loading=False
        self.unloading=False     
        self.u=True
        self.idle=True
        self.travelling=True
        self.check_for_breakdown=False
        self.Mdock=False
        self.machine_reply=None
        self.MachineData=None
        self.unloading_dock_response=False 
        self.dock=False

    class AMRFSM(FSMBehaviour):
        async def on_start(self):
            print("AMR1 FSM started.")

        async def on_end(self):
            print("AMR1 FSM finished.")

    class Ready(State):
        async def run(self):
            await asyncio.sleep(8)
            print("AMR1 is Ready")
            register = Message(to="scheduler@jabber.fr")
            register.set_metadata("performative", "Register")
            register.body = "robot1@jabber.fr"
            await self.send(register)  # Sending the register message
            await asyncio.sleep(2)
            msg1 = await self.receive(timeout=None)
            if msg1:
                performative = msg1.get_metadata("performative")
                if performative == "inform" and msg1.body == "Registered":
                    print("Successfully Registered")
                    self.set_next_state("waitingfor_jobset")
                else:
                    print("Failed to register. Staying in Ready state.")
            else:
                print("No response from scheduler. Staying in Ready state.")
                self.set_next_state("Ready")

    class waitingfor_jobset(State):
        async def run(self):
            while self.agent.waiting_for_job==True: 
                ask=Message(to="loadingdock@jabber.fr")
                ask.set_metadata("performative", "ask")
                ask.body = "my_job_set"
                print(ask.body)
                await self.send(ask)
                await asyncio.sleep(2)      
                # print("waitingforjob")
                job=await self.receive(timeout=10)
                if job:
                    performative=job.get_metadata("performative")
                    if performative=="loading_dock_ready":
                        try:
                            my_job = json.loads(job.body)
                            if isinstance(my_job, list):
                                print(f"Received Job: {my_job}")
                                job = [str(element) for element in my_job]
                                self.agent.remainingjobs=deque(my_job)
                                self.agent.waiting_for_job=False
                                self.set_next_state("loading")
                            else:
                                print("Error: Received data is not a valid coordinate.")
                                self.set_next_state("waitingfor_jobset")
                        except json.JSONDecodeError:
                            print("Error: Unable to decode message body as JSON.")
                            self.set_next_state("waitingfor_jobset")

    
    class Loading(State):
        async def run(self):
            if self.agent.going_to_loading==True:    
                print("Going to Loading Dock")
                self.agent.machine = -1
                self.agent.ptime = 3
                self.set_next_state("Processing")

            if self.agent.loading==True:        
                ask=Message(to="loadingdock@jabber.fr")
                ask.set_metadata("performative", "ask")
                ask.body = "load_the_job"
                print(ask.body)
                await self.send(ask)
                await asyncio.sleep(10)            
                my_job=await self.receive(timeout=200)
                if my_job:
                    print("waiting for Loading Agent response")
                    performative = my_job.get_metadata("performative")
                    if performative=="loading" and my_job.body=="loading_completed":
                        self.agent.loading=False
                        print("Job Loading Completed")
                        self.agent.idle=True
                        self.set_next_state("Idle")
                # else:
                #     self.set_next_state("loading")

    class Unloading(State):
        async def run(self):
            if self.agent.going_to_unloading==True:
                # print("Going to Unoading Dock")
                while self.agent.unloading_dock_response==False:
                    ask=Message(to="unloadingdock@jabber.fr")
                    ask.set_metadata("performative", "ask")
                    ask.body = "need to unload"
                    print(ask.body)
                    await self.send(ask)
                    my_job=await self.receive(timeout=200)
                    if my_job:
                        if my_job.get_metadata("performative") == "unload" and my_job.body == "come to unloading dock":
                            self.agent.unloading_dock_response=True
                            self.agent.machine = -2
                            # self.agent.ptime = 3
                            self.set_next_state("Processing")

                        elif my_job.get_metadata("performative") == "unload" and my_job.body == "come to unloading Q dock":
                            self.agent.unloading_dock_response=True
                            self.agent.machine = -22
                            # self.agent.ptime = 3
                            self.set_next_state("Processing")


            if self.agent.unloading==True:        
                ask=Message(to="unloadingdock@jabber.fr")
                ask.set_metadata("performative", "ask")
                ask.body = "unload_the_job"
                print(ask.body)
                await self.send(ask)
                await asyncio.sleep(5)            
                my_job=await self.receive(timeout=200)
                if my_job:
                    print("waiting for Loading Agent response")
                    performative = my_job.get_metadata("performative")
                    if performative=="unloading" and my_job.body=="unloading_completed":
                        self.agent.unloading=False
                        print("Job Unloading Completed")
                        if self.agent.remainingjobs==None:
                            print("No Jobs remaining, going to dock")
                            self.set_next_state("Dock")
                        else:
                             print("going to loading agent to process next job")
                             self.agent.going_to_loading=True
                             self.agent.loading=False
                             self.set_next_state("loading")
            #         else:
            #             self.set_next_state("unloading")
            # else:
            #     self.set_next_state("unloading")


    class Idle(State):
        async def run(self):
            if self.agent.check_for_breakdown==True:
                print("Checking for any Breakdown issue")
                breakdown_msg=await self.receive(timeout=10)
                if breakdown_msg:
                    performative = breakdown_msg.get_metadata("performative")
                    if performative=="user_input" and breakdown_msg.body=="Breakdown":
                        self.set_next_state("Breakdown")
                else:
                    print("No Breakdown")
                    self.agent.idle=False
                    self.agent.travelling=True
                    self.set_next_state("unloading")

            else:
                if self.agent.remainingjobs:
                    while self.agent.idle==True:
                        await asyncio.sleep(4)
                        reply = Message(to=self.agent.JobsAgents[str(self.agent.remainingjobs[0])])
                        reply.set_metadata("performative", "ask_for_op")
                        reply.body = "Idle"
                        await self.send(reply)
                        print("Sent Idle status to Job Agent", self.agent.JobsAgents[str(self.agent.remainingjobs[0])])
                        
                        msg = await self.receive(timeout=25)
                        if msg:
                            performative = msg.get_metadata("performative")
                            if performative == "job_orders":
                                try:
                                    data2 = json.loads(msg.body)
                                    machine=data2[0]
                                    ptime=data2[1]
                                    # MachineData=[self.agent.RRJobAgents[self.agent.JobsAgents[self.agent.remainingjobs[0]]],ptime]
                                    self.agent.MachineData=[self.agent.remainingjobs[0],ptime]
                                    print(f"Received coordinates: {machine}")
                                    askmachine = Message(to=self.agent.MachineAgents[str(machine)])
                                    askmachine.set_metadata("performative", "ask_machine_for_processing") 
                                    askmachine.body = str(self.agent.MachineData[0])
                                    await self.send(askmachine)
                                    print('confirming idle machine from',self.agent.MachineAgents[str(machine)])
                                    await asyncio.sleep(1)

                                    # machine_reply=await self.receive(timeout=120)
                                    # print('got machine reply', machine_reply.body, 'from ', machine_reply.sender)
                                    # if machine_reply and machine_reply.sender.bare in self.agent.RMachineAgents.keys():
                                    #     self.agent.machine_reply=machine_reply.sender
                                    #     performative=machine_reply.get_metadata("performative")
                                    #     if performative=="machine_reply" and machine_reply.body=="Yes":


                                    self.agent.idle=False
                                    #checkout for error
                                    print('machine:', machine)
                                    self.agent.machine = machine
                                    self.agent.ptime = ptime
                                    self.set_next_state("Processing")

                                    # else:
                                    #     self.set_next_state("Idle")  
                                    
                       
                                except json.JSONDecodeError:
                                    print("Error: Unable to decode message body as JSON.")
                                    self.set_next_state("Idle")

                            elif performative=="inform_amr" and msg.body=="tasks are done":
                                print("received task completed msg from",msg.sender)
                                self.agent.remainingjobs.popleft()
                                self.agent.idle=False
                                self.agent.going_to_unloading=True
                                self.agent.travelling=True
                                self.agent.unloading=False
                                self.set_next_state("unloading")
                        else:
                            print("No Message Received")
                            self.set_next_state("Idle")

                    while self.agent.travelling==False:
                        await asyncio.sleep(2)            
                        tellmachine=Message(to=self.agent.MachineAgents[str(self.agent.machine)])
                        tellmachine.set_metadata("performative","waiting_for_machine_to_process")
                        tellmachine.body="Ready"
                        print("sending",tellmachine.body,"to machine",self.agent.MachineAgents[str(self.agent.machine)])
                        await self.send(tellmachine)
                        await asyncio.sleep(1)
                        machine_finish=await self.receive(timeout=60)
                        if machine_finish:
                            performative=machine_finish.get_metadata("performative")
                            print("Machine Processing")
                            if performative=="machine_reply" and machine_finish.body=="Processing complete":
                                print("Maching Processing completed")
                                self.agent.travelling=True
                                self.agent.idle=True
                                self.set_next_state("Idle")
                        else:
                            self.set_next_state("Idle")





                # if isinstance(machine, int):
                #     print(f"Received coordinates: {machine}")
                #     self.agent.machine = machine
                #     self.agent.ptime = ptime
                #     self.set_next_state("Processing")
                # else:
                #     print("Error: Received data is not a valid coordinate.")
                #     self.set_next_state("Idle")

    class Processing(State):
        async def run(self):
            print("Going to",self.agent.Workstations[str(self.agent.machine)])
            pose=self.agent.machine


            m1 = [-3.32, 6.65]
            m1_Mdock=[-4.5,7.43]
            m2 = [-3.38, 1.46]
            m2_Mdock=[-4.5,0.47]
            m3 = [1.627, 6.459]
            m3_Mdock=[0.55,7.5]
            m4 = [1.681, 1.407]
            m4_Mdock=[0.55,0.002]
            loading_dock = [-6.69, 4.028]
            unloading_dock = [3.52, 3.96]
            unloading_Q_dock=[4.36,0.79]
            robot1_charging_dock=[-7.47,0.86]
            robot2_charging_dock=[-7.47,7.22]
            robot3_charging_dock=[4.28,7.41]

            poses = {
                '0': m1,
                '0d':m1_Mdock,
                '1': m2,
                '1d':m2_Mdock,
                '2': m3,
                '2d':m3_Mdock,
                '3': m4,
                '3d':m4_Mdock,
                '-1':loading_dock,
                '-2':unloading_dock,
                '-22':unloading_Q_dock,
                '11':robot1_charging_dock,
                '22':robot2_charging_dock,
                '33':robot3_charging_dock
            }

            goal_pose = PoseStamped()
            goal_pose.header.frame_id = 'map'
            goal_pose.header.stamp = self.agent.navigator.get_clock().now().to_msg()
            goal_pose.pose.position.x = poses[str(pose)][0]
            goal_pose.pose.position.y = poses[str(pose)][1] 
            goal_pose.pose.orientation.w = 1.0
            print("start navigation")

            self.agent.navigator.goToPose(goal_pose)
            while not self.agent.navigator.isTaskComplete():
                time.sleep(1)
            print("give result")
            result = self.agent.navigator.getResult()
            if result == TaskResult.SUCCEEDED:
                if self.agent.machine==-1:
                    print("Reached Loading Dock")
                    self.agent.going_to_loading=False
                    self.agent.loading=True
                    self.set_next_state("loading")

                elif self.agent.machine==-2:
                    print("Reached Unloading Dock")
                    # self.agent.check_for_breakdown=True
                    self.agent.going_to_unloading=False
                    self.agent.unloading=True
                    self.set_next_state("unloading")

                elif self.agent.machine==-22:
                    print("Reached unloading dock Queue")
                    self.agent.unloading_dock_response=False
                    self.agent.going_to_unloading=True
                    self.agent.unloading=False
                    self.set_next_state("unloading")

                elif self.agent.machine==11:
                    print("Reached charging dock")
                    self.agent.dock=True
                    self.set_next_state("Dock")

                else:
                    print(f"Reached Machine: {self.agent.machine}") 
                    self.agent.travelling=False
                    self.set_next_state("Idle")  # Return to Idle after processing

            elif result == TaskResult.CANCELED:
                print('Inspection of shelving was canceled. Returning to start...')
                exit(1)
                
            elif result == TaskResult.FAILED:
                print('Inspection of shelving failed! Returning to start...')
            

    class Breakdown(State):
        async def run(self):
            print("State: Breakdown. Sending JID of assistance agent...")
            msg = Message(to="scheduler@jabber.fr")
            msg.set_metadata("performative", "Breakdown: please assist")
            msg.body = "robot1@jabber.fr"
            await self.send(msg)
            print("Breakdown message sent to another agent.")
            self.set_next_state("Idle")


    class Dock(State):
        async def run(self):
            print("In Dock")
            if self.agent.dock==False:
                self.agent.machine==11
                self.set_next_state("Processing")
            else:
                my_job=await self.receive(timeout=100)
                if my_job:
                    if my_job.get_metadata("performative") == "new_job" and my_job.body == "get ready":
                        self.set_next_state("Ready")
                    else:
                        self.set_next_state("Dock")
                else:
                    self.set_next_state("Dock")


    async def setup(self):
        self.navigator = BasicNavigator(namespace="robot1")
        fsm = self.AMRFSM()
        #All the States
        fsm.add_state(name="Ready", state=self.Ready(), initial=True)
        fsm.add_state(name="waitingfor_jobset", state=self.waitingfor_jobset())
        fsm.add_state(name="loading", state=self.Loading())
        fsm.add_state(name="unloading", state=self.Unloading())
        fsm.add_state(name="Idle", state=self.Idle())
        fsm.add_state(name="Dock", state=self.Dock())
        fsm.add_state(name="Processing", state=self.Processing())
        fsm.add_state(name="Breakdown", state=self.Breakdown())

        # Transition from one State to another State
        fsm.add_transition(source="Ready", dest="Ready")
        fsm.add_transition(source="waitingfor_jobset", dest="Ready")
        fsm.add_transition(source="Ready", dest="waitingfor_jobset")

        fsm.add_transition(source="waitingfor_jobset", dest="waitingfor_jobset")
        fsm.add_transition(source="waitingfor_jobset", dest="loading")

        fsm.add_transition(source="loading", dest="loading")
        fsm.add_transition(source="Processing", dest="loading")
        fsm.add_transition(source="loading", dest="Processing")
        fsm.add_transition(source="loading", dest="Idle")

        fsm.add_transition(source="Idle", dest="Idle")
        fsm.add_transition(source="Idle", dest="Processing")
        fsm.add_transition(source="Processing", dest="Idle")

        fsm.add_transition(source="Idle", dest="Breakdown")
        fsm.add_transition(source="Breakdown", dest="Idle")
        fsm.add_transition(source="Processing", dest="Breakdown")

        fsm.add_transition(source="Processing", dest="unloading")
        fsm.add_transition(source="unloading", dest="Processing")
        fsm.add_transition(source="unloading", dest="Dock")
        fsm.add_transition(source="unloading", dest="loading")
        fsm.add_transition(source="unloading", dest="unloading")
        fsm.add_transition(source="Idle", dest="unloading")

        fsm.add_transition(source="Idle", dest="Dock")
        fsm.add_transition(source="Dock", dest="Idle")
        fsm.add_transition(source="Dock", dest="Dock")
        fsm.add_transition(source="Dock", dest="Ready")

        self.add_behaviour(fsm)

        # Register handlers for XMPP version and disco queries
        self.presence.version_handler = self.version_query_handler
        self.presence.disco_info_handler = self.disco_info_query_handler

    def version_query_handler(self, iq):
        iq.make_result()
        version_data = version.xso.Query()
        version_data.name = "AMR1"
        version_data.version = "1.0"
        iq.payload = version_data
        return iq

    def disco_info_query_handler(self, iq):
        iq.make_result()
        disco_data = disco.xso.InfoQuery()
        # Add features or identities that your agent supports
        iq.payload = disco_data
        return iq


if __name__ == "__main__":
    amr1 = AMR1("robot1@jabber.fr", "changeme")

    async def run():
        await amr1.start()
        amr1.web.start(hostname="127.0.0.1", port="10001")
        print("AMR1 started")

        try:
            while amr1.is_alive():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await amr1.stop()

    asyncio.run(run())