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

class AMR2(Agent):
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
        self.waiting_for_job=True
        self.going_to_loading=True
        self.loading=False
        self.u=True
        self.idle=True
        self.travelling=True
        self.check_for_breakdown=False
        self.Mdock=False

    class AMRFSM(FSMBehaviour):
        async def on_start(self):
            print("AMR2 FSM started.")

        async def on_end(self):
            print("AMR2 FSM finished.")

    class Ready(State):
        async def run(self):
            await asyncio.sleep(8)
            print("AMR2 is Ready")
            register = Message(to="scheduler@jabber.fr")
            register.set_metadata("performative", "Register")
            register.body = "robot2@jabber.fr"
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
            rclpy.init()
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
                                print(f"Received coordinates: {my_job}")
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
            while self.agent.going_to_loading==True:    
                print("Going to Loading Dock")
                self.agent.machine = -1
                self.agent.ptime = 3
                self.set_next_state("Processing")

            while self.agent.loading==True:        
                ask=Message(to="loadingdock@jabber.fr")
                ask.set_metadata("performative", "ask")
                ask.body = "load_the_job"
                print(ask.body)
                await self.send(ask)            
                my_job=await self.receive(timeout=None)
                if my_job:
                    print("waiting for jobs")
                    performative = my_job.get_metadata("performative")
                    if performative=="loading" and my_job.body=="loading_completed":
                        print("Job Loading Completed")
                        self.set_next_state("Idle")


    class Idle(State):
        async def run(self):
            if self.agent.check_for_breakdown==True:
                print("Checking for any Breakdown issue")
                breakdown_msg=await self.receive(timeout=20)
                if breakdown_msg:
                    performative = breakdown_msg.get_metadata("performative")
                    if performative=="user_input" and breakdown_msg.body=="Breakdown":
                        self.set_next_state("Breakdown")

            else:
                if self.agent.remainingjobs:
                    while self.agent.idle==True:
                        reply = Message(to=self.agent.JobsAgents[self.agent.remainingjobs[0]])
                        reply.set_metadata("performative", "ask_for_op")
                        reply.body = "Idle"
                        await self.send(reply)
                        print("Sent Idle status to Job Agent.")
                        await asyncio.sleep(1)
                        msg = await self.receive(timeout=10)
                        if msg:
                            performative = msg.get_metadata("performative")
                            if performative == "job_orders":
                                try:
                                    data2 = json.loads(msg.body)
                                    machine=data2[0]
                                    ptime=data2[1]
                                    # MachineData=[self.agent.RRJobAgents[self.agent.JobsAgents[self.agent.remainingjobs[0]]],ptime]
                                    MachineData=[self.agent.remainingjobs[0],ptime]
                                    print(f"Received coordinates: {machine}")
                                    askmachine = Message(to=self.agent.MachineAgents[str(machine)])
                                    askmachine.set_metadata("performative", "ask_machine") 
                                    askmachine.body = "canIcome"
                                    await self.send(askmachine)
                                    await asyncio.sleep(4)
                                    machine_reply=await self.receive(timeout=None)
                                    if machine_reply:
                                        performative=machine_reply.get_metadata("performative")
                                        if performative=="machine_reply" and machine_reply.body=="Yes":
                                            self.agent.idle=False
                                            #checkout for error
                                            self.agent.machine = self.agent.RMachineAgents[self.agent.MachineAgents[self.agent.remainingjobs[0]]]
                                            self.agent.ptime = ptime
                                            self.set_next_state("Processing")
                                        elif performative=="machine_reply" and machine_reply=="Come to Machine Dock":
                                            self.agent.dock=True
                                    else:
                                        self.set_next_state("Idle")     
                                except json.JSONDecodeError:
                                    print("Error: Unable to decode message body as JSON.")
                                    self.set_next_state("Idle")

                            elif performative=="inform_amr" and msg.body=="tasks are done":
                                self.agent.remainingjobs.popleft()
                                print("Going to Unloading Dock")
                                self.agent.machine = -2
                                self.agent.ptime = 3
                                self.set_next_state("Processing")
                        else:
                            print("No Message Received")
                            self.set_next_state("Idle")

                    while self.agent.travelling==False:
                        await asyncio.sleep(2)            
                        tellmachine=Message(to=machine_reply.sender)
                        tellmachine.set_metadata("performative","waiting_for_machine_to_process")
                        tellmachine.body=json.dumps(MachineData)
                        await self.send(tellmachine)
                        await asyncio.sleep(1)
                        machine_finish=await self.receive(timeout=60)
                        if machine_finish:
                            performative=machine_finish.get_metadata("performative")
                            if performative=="machine_finish" and machine_finish.body=="machingdone":
                                print("Maching Processing completed")
                                self.agent.travelling=True
                                self.agent.idle=True
                                self.set_next_state("Idle")
                        else:
                            self.set_next_state("Idle")

                    while self.agent.dock==True:
                        msg2=await self.receive(timeout=None)
                        if msg2:
                            performative=msg2.get_metadata("performative")
                            if performative=="machine_reply" and msg2.body=="Yes":
                                self.agent.idle=False
                                self.agent.dock=False
                                #checkout for error
                                self.agent.machine = self.agent.RMachineAgents[self.agent.MachineAgents[self.agent.remainingjobs[0]]]
                                self.agent.ptime = ptime
                                self.set_next_state("Processing")






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
            print(f"State: Processing coordinates: {self.agent.machine}")
            print(f"State: Processing Time: {self.agent.ptime}")
            await asyncio.sleep(self.agent.ptime + 2)
            self.set_next_state("Idle")
            rclpy.init()
            pose=self.agent.machine
            navigator = BasicNavigator()

            m1 = [-3.32, 6.65]
            m2 = [-3.38, 1.46]
            m3 = [1.627, 6.459]
            m4 = [1.681, 1.407]
            loading_dock = [-6.69, 4.028]
            unloading_dock = [3.52, 3.96]

            poses = {
                '0': m1,
                '1': m2,
                '2': m3,
                '3': m4,
                '-1': loading_dock,
                '-2': unloading_dock
            }

            goal_pose = PoseStamped()
            goal_pose.header.frame_id = 'map'
            goal_pose.header.stamp = navigator.get_clock().now().to_msg()
            goal_pose.pose.position.x = poses[str(pose)][0]
            goal_pose.pose.position.y = poses[str(pose)][1] 
            goal_pose.pose.orientation.w = 1.0

            navigator.goToPose(goal_pose)

            result = navigator.getResult()
            if result == TaskResult.SUCCEEDED:
                if self.agent.machine==-1:
                    print("Reached Loading Dock")
                    self.agent.going_to_loading=False
                    self.agent.loading=True
                    self.set_next_state("loading")
                elif self.agent.machine==-2:
                    print("Reached Unloading Dock")
                    self.agent.check_for_breakdown=True
                    if self.agent.remainingjobs==None:
                        self.set_next_state("Dock")
                    else:
                        self.set_next_state("Idle")
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
            msg.body = "robot2@jabber.fr"
            await self.send(msg)
            print("Breakdown message sent to another agent.")
            self.set_next_state("Idle")

    class Dock(State):
        async def run(self):
            print("Going to Docking station")
            msg1 = await self.receive(timeout=None)
            if msg1:
                performative = msg1.get_metadata("performative")
                if performative == "inform" and msg1.body=="New Schedule":   
                    self.set_next_state("Idle")

    async def setup(self):
        fsm = self.AMRFSM()
        #All the States
        fsm.add_state(name="Ready", state=self.Ready(), initial=True)
        fsm.add_state(name="waitingfor_jobset", state=self.waitingfor_jobset())
        fsm.add_state(name="loading", state=self.Loading())
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

        fsm.add_transition(source="Idle", dest="Dock")
        fsm.add_transition(source="Dock", dest="Idle")
        fsm.add_transition(source="Dock", dest="Dock")

        self.add_behaviour(fsm)

        # Register handlers for XMPP version and disco queries
        self.presence.version_handler = self.version_query_handler
        self.presence.disco_info_handler = self.disco_info_query_handler

    def version_query_handler(self, iq):
        iq.make_result()
        version_data = version.xso.Query()
        version_data.name = "AMR2"
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
    amr2 = AMR2("robot2@jabber.fr", "changeme")

    async def run():
        await amr2.start()
        print("AMR2 started")

        try:
            while amr2.is_alive():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await amr2.stop()

    asyncio.run(run())
