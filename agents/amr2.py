from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State, CyclicBehaviour
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
# from tf.tf_transformations import euler_from_quaternion
from geometry_msgs.msg import TransformStamped
import tf2_ros

from rclpy.node import Node
from nav_msgs.msg import Odometry
import threading



if not rclpy.ok():  # Ensure rclpy.init() is called only once
    rclpy.init()


# class OdomSubscriber(Node):

#     def __init__(self):
#         super().__init__('robot2_odom_subscriber')
#         # Subscribe to the /odom topic
#         self.subscription = self.create_subscription(
#             Odometry,
#             '/robot2/odom',  # Topic name
#             self.odom_callback,  # Callback function
#             10  # QoS profile, 10 is a common choice
#         )
#         self.subscription  # Prevents the subscription from being garbage collected
        
#         # Store the latest odometry data
#         self.current_odom = None

#     def odom_callback(self, msg):
#         # Update the current odometry with the latest message
#         self.current_odom = msg
#         position = msg.pose.pose.position
#         # orientation = msg.pose.pose.orientation
#         # self.get_logger().info(f"Position: x={position.x}, y={position.y}, z={position.z}")
#         # self.get_logger().info(f"Orientation: x={orientation.x}, y={orientation.y}, z={orientation.z}, w={orientation.w}")

#     def get_current_odom(self):
#         # Function to return the latest stored odometry data
#         if self.current_odom:
#             return self.current_odom.pose.pose
#         else:
#             return None
        
#     def spin_in_background(self):
#         # Run the node in a separate thread
#         spin_thread = threading.Thread(target=rclpy.spin, args=(self,), daemon=True)
#         spin_thread.start()


class AMR2(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


        self.remainingjobs=deque()
        self.completed_jobs = []
        self.JobsAgents={
            '0':"job1@jabber.fr",
            '1':"job2@jabber.fr",
            '2':"job3@jabber.fr",
            '3':"job4@jabber.fr",
            '4':"job5@jabber.fr",
            '5':"job6@jabber.fr"
        }
        self.RRJobAgents={
            "job1@jabber.fr":'0',
            "job2@jabber.fr":'1',
            "job3@jabber.fr":'2',
            "job4@jabber.fr":'3',
            "job5@jabber.fr":'4',
            "job6@jabber.fr":'5'
        }
        self.MachineAgents={
            '0':"machine1@jabber.fr",
            '1':"machine2@jabber.fr",
            '2':"machine3@jabber.fr",
            '3':"machine4@jabber.fr",
            '4':"machine5@jabber.fr",
            '5':"machine6@jabber.fr"
        }
        self.RMachineAgents={
            "machine1@jabber.fr":'0',
            "machine2@jabber.fr":'1',
            "machine3@jabber.fr":'2',
            "machine4@jabber.fr":'3',
            "machine5@jabber.fr":'4',
            "machine6@jabber.fr":'5',
        }
        self.Workstations = {
                '0': 'machine0',
                '0d':'machine0 dock',
                '1': 'machine1',
                '1d':'machine1 dock',
                '2': 'machine2',
                '2d':'machine2 dock',
                '3': 'machine3',
                '3d':'machine3 dock',
                '4': 'machine4',
                '4d':'machine4 dock',
                '5': 'machine5',
                '5d':'machine5 dock',
                '-1': 'loading_dock',
                '-11':'unloading Q dock',
                '-2': 'unloading_dock',
                '-22':'unloading_Q_dock',
                '11':'robot1_charging_dock',
                '22':'robot2_charging_dock',
                '33':'robot3_charging_dock',
                '44':'robot4_charging_dock'
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
        self.in_machine_dock=False
        self.breakdown=False
        self.amr_location=0




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
                            if isinstance(my_job, list) :
                                if my_job!=[]:
                                    print(f"Received Job: {my_job}")
                                    job = [str(element) for element in my_job]
                                    self.agent.remainingjobs=deque(my_job)
                                    self.agent.waiting_for_job=False
                                    self.set_next_state("loading")
                                else:
                                    self.set_next_state("Dock")
                            else:
                                print("Error: Received data is not a valid coordinate.")
                                self.set_next_state("waitingfor_jobset")

                        except json.JSONDecodeError:
                            print("Error: Unable to decode message body as JSON.")
                            self.set_next_state("waitingfor_jobset")
                            
                    elif job.get_metadata("performative") == "no jobs remaining" and job.body == "wait for new job assignment":
                        print("No Jobs Remaining wait in Dock")
                        self.set_next_state("wait_for_newjobs")
                        self.agent.waiting_for_job=False



    class wait_for_newjobs(State):
        async def run(self):
            ask1=await self.receive(timeout=30)
            if ask1:
                if ask1.get_metadata("performative") == "ask" and ask1.body=="available" :
                    tell=Message(to=str(ask1.sender))
                    tell.set_metadata("performative", "tell")
                    tell.body = "yes"
                    print(tell.body)
                    await self.send(tell)
                    job=await self.receive(timeout=45)
                    if job:
                        if job.get_metadata("performative") == "new jobs" :
                            self.agent.amr_location=json.loads(job.body)

                            ask=Message(to=str(job.sender))
                            ask.set_metadata("performative", "ask")
                            ask.body = "send jobs"
                            print(ask.body)
                            await self.send(ask)

                            jobs=await self.receive(timeout=45)
                            if jobs:
                                if jobs.get_metadata("performative") == "jobs" :
                                    job1s=json.loads(jobs.body)
                                    self.agent.remainingjobs=deque(job1s)
                                    await asyncio.sleep(3) 

                                    goal_pose = PoseStamped()
                                    goal_pose.header.frame_id = 'map'
                                    goal_pose.header.stamp = self.agent.navigator.get_clock().now().to_msg()
                                    goal_pose.pose.position.x = self.agent.amr_location[0]
                                    goal_pose.pose.position.y = self.agent.amr_location[1]
                                    goal_pose.pose.orientation.w = 1.0
                                    print("start navigation")

                                    self.agent.navigator.goToPose(goal_pose)
                                    while not self.agent.navigator.isTaskComplete():
                                        time.sleep(1)
                                    print("give result")
                                    result = self.agent.navigator.getResult()
                                    if result == TaskResult.SUCCEEDED:
                                        print("Load the job")
                                        await asyncio.sleep(4)
                                        self.set_next_state("Idle")  
                                        
                                    elif result == TaskResult.CANCELED:
                                        print('Inspection of shelving was canceled. Returning to start...')
                                        exit(1)
                                        
                                    elif result == TaskResult.FAILED:
                                        print('Inspection of shelving failed! Returning to start...')
            
                else:
                    self.set_next_state("wait_for_newjobs")
            else:
                self.set_next_state("wait_for_newjobs")
    
    class Loading(State):
        async def run(self):
            if self.agent.going_to_loading==True:    
                print("Going to Loading Dock")
                self.agent.machine = '-1'
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
                            self.agent.machine = '-2'
                            # self.agent.ptime = 3
                            self.set_next_state("Processing")

                        elif my_job.get_metadata("performative") == "unload" and my_job.body == "come to unloading Q dock":
                            self.agent.unloading_dock_response=True
                            self.agent.machine = '-22'
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
                            self.agent.dock=False
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
                                    machine=str(data2[0])
                                    ptime=data2[1]
                                    # MachineData=[self.agent.RRJobAgents[self.agent.JobsAgents[self.agent.remainingjobs[0]]],ptime]

                                    self.agent.MachineData=[self.agent.remainingjobs[0],ptime]
                                    print(f"Received coordinates: {machine}")
                                    machinereply=False
                                    while machinereply==False:
                                        askmachine = Message(to=self.agent.MachineAgents[machine])
                                        askmachine.set_metadata("performative", "ask_machine") 
                                        askmachine.body="canIcome"
                                        await self.send(askmachine)
                                    

                                        machine_reply= await self.receive(timeout=30)
                                        if machine_reply:
                                            if machine_reply.get_metadata("performative") == "machine_reply" and machine_reply.body == "Yes":
                                                self.agent.idle=False
                                                machinereply=True
                                                #checkout for error
                                                print('machine:', machine)
                                                self.agent.machine = machine
                                                self.agent.ptime = ptime
                                                self.set_next_state("Processing")
                                            elif machine_reply.get_metadata("performative") == "machine_reply" and machine_reply.body == "come_to_machine_dock":
                                                self.agent.idle=False
                                                machinereply=True
                                                #checkout for error
                                                print('machine:', machine,"dock")
                                                self.agent.machine = machine+'d'
                                                self.agent.ptime = ptime
                                                self.set_next_state("Processing")
                                            
                                    

                                    # askmachine.set_metadata("performative", "ask_machine_for_processing") 
                                    # askmachine.body = str(self.agent.MachineData[0])
                                    # await self.send(askmachine)
                                    # print('confirming idle machine from',self.agent.MachineAgents[machine])
                                    # await asyncio.sleep(1)
                       
                                except json.JSONDecodeError:
                                    print("Error: Unable to decode message body as JSON.")
                                    self.set_next_state("Idle")

                            elif performative=="inform_amr" and msg.body=="tasks are done":
                                print("received task completed msg from",msg.sender)
                                self.agent.remainingjobs.popleft()
                                if len(self.agent.remainingjobs)==0:
                                    self.agent.remainingjobs=None
                                print(self.agent.remainingjobs,"are remaining jobs")
                                self.agent.idle=False
                                self.agent.unloading_dock_response=False
                                self.agent.going_to_unloading=True
                                self.agent.travelling=True
                                self.agent.unloading=False
                                self.set_next_state("unloading")
                        else:
                            print("No Message Received")
                            self.set_next_state("Idle")


                    while self.agent.in_machine_dock==True:
                        print("in machine",self.agent.machine)
                        self.agent.machine = self.agent.machine[:1]
                        tellmachine=Message(to=self.agent.MachineAgents[self.agent.machine])
                        tellmachine.set_metadata("performative", "ask_machine") 
                        tellmachine.body="canIcome"
                        await self.send(tellmachine)
                        machine_reply= await self.receive(timeout=30)
                        if machine_reply:
                            if machine_reply.get_metadata("performative") == "machine_reply" and machine_reply.body == "Yes":
                                self.agent.in_machine_dock=False
                                #checkout for error
                                print('machine:', self.agent.machine)
                                # self.agent.machine = self.agent.machine[:1]
                                # self.agent.ptime = ptime
                                self.set_next_state("Processing")


                    while self.agent.travelling==False:
                        await asyncio.sleep(2)            
                        tellmachine=Message(to=self.agent.MachineAgents[self.agent.machine])
                        tellmachine.set_metadata("performative","waiting_for_machine_to_process")
                        tellmachine.body="Ready"
                        print("sending",tellmachine.body,"to machine",self.agent.MachineAgents[self.agent.machine])
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
            print("Going to",self.agent.Workstations[self.agent.machine])
            pose=self.agent.machine


            #for 4 machine
            m1 = [-4.5,8.3]
            m1_Mdock=[-4.5,11.0]
            m2 = [-4.5, 2.9]
            m2_Mdock=[-4.5,-0.06]
            m3 = [1.5, 8.3]
            m3_Mdock=[1.5,11.0]
            m4 = [1.5,2.7 ]
            m4_Mdock=[1.5,-0.04]
            m5 = [1.5,2.7 ]
            m5_Mdock=[1.5,-0.04]
            m6 = [1.5,2.7 ]
            m6_Mdock=[1.5,-0.04]
            loading_dock = [-9.15,5.11]
            loading_Q_dock = [-10,9.4]
            unloading_dock = [7.32,5.2]
            unloading_Q_dock=[9.5,0.637]
            robot1_charging_dock=[-6.5,-6.8]
            robot2_charging_dock=[-8.53,-7.03]
            robot3_charging_dock=[-10.09,-6.84]
            robot4_charging_dock=[-11.08,-4.77]

            #for 6 machine
            # m1 = [-6.0,7.9]
            # m1_Mdock=[-6.0,11.1]
            # m2 = [-4.65,3.15]
            # m2_Mdock=[-4.5,-0.02]
            # m3 = [-1.4,7.88]
            # m3_Mdock=[-1.4,11.1]
            # m4 = [-0.3,3.23 ]
            # m4_Mdock=[-0.3,-0.034]
            # m5 = [3.61,7.7 ]
            # m5_Mdock=[3.6,11.22]
            # m6 = [3.3, 3.21]
            # m6_Mdock=[3.3,0.01]
            # loading_dock = [-9.15,5.11]
            # loading_Q_dock = [-10.0,9.4]
            # unloading_dock = [7.32,5.2]
            # unloading_Q_dock=[9.5,0.637]
            # robot1_charging_dock=[-6.5,-6.8]
            # robot2_charging_dock=[-8.53,-7.03]
            # robot3_charging_dock=[-10.09,-6.84]
            # robot4_charging_dock=[-11.08,-4.77]


            poses = {
                '0': m1,
                '0d':m1_Mdock,
                '1': m2,
                '1d':m2_Mdock,
                '2': m3,
                '2d':m3_Mdock,
                '3': m4,
                '3d':m4_Mdock,
                '4': m5,
                '4d':m5_Mdock,
                '5': m6,
                '5d':m6_Mdock,
                '-1':loading_dock,
                '-11':loading_Q_dock,
                '-2':unloading_dock,
                '-22':unloading_Q_dock,
                '11':robot1_charging_dock,
                '22':robot2_charging_dock,
                '33':robot3_charging_dock,
                '44':robot4_charging_dock
            }

            goal_pose = PoseStamped()
            goal_pose.header.frame_id = 'map'
            goal_pose.header.stamp = self.agent.navigator.get_clock().now().to_msg()
            goal_pose.pose.position.x = poses[pose][0]
            goal_pose.pose.position.y = poses[pose][1]
            goal_pose.pose.orientation.w = 1.0
            print("start navigation")

            self.agent.navigator.goToPose(goal_pose)
            while not self.agent.navigator.isTaskComplete():
                time.sleep(1)
            print("give result")
            result = self.agent.navigator.getResult()
            if result == TaskResult.SUCCEEDED:
                if self.agent.machine=='-1':
                    print("Reached Loading Dock")
                    self.agent.going_to_loading=False
                    self.agent.loading=True
                    self.set_next_state("loading")

                elif self.agent.machine=='-2':
                    print("Reached Unloading Dock")
                    # self.agent.check_for_breakdown=True
                    self.agent.going_to_unloading=False
                    self.agent.unloading=True
                    self.set_next_state("unloading")

                elif self.agent.machine=='-22':
                    print("Reached unloading dock Queue")
                    self.agent.unloading_dock_response=False
                    self.agent.going_to_unloading=True
                    self.agent.unloading=False
                    self.set_next_state("unloading")

                elif self.agent.machine=='11':
                    print("Reached charging dock")
                    self.agent.dock=True
                    self.set_next_state("Dock")

                elif self.agent.machine=='0d' or self.agent.machine=='1d' or self.agent.machine=='2d' or self.agent.machine=='3d' or self.agent.machine=='4d' or self.agent.machine=='5d':
                    print("Reached machine",self.agent.machine)
                    self.agent.in_machine_dock=True
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
            

    # class Breakdown(CyclicBehaviour):
    #     async def run(self):

    #         if self.agent.breakdown==False:
    #             print("Checking for any Breakdown issue")
    #             breakdown_msg=await self.receive(timeout=50)
    #             if breakdown_msg:
    #                 performative = breakdown_msg.get_metadata("performative")
    #                 if performative=="user_input" and breakdown_msg.body=="Breakdown":
    #                     # rclpy.spin_once(self.agent.odom_sub)
    #                     self.agent.breakdown=True
    #                     odom = self.agent.odom_sub.get_current_odom()
    #                     if odom:
    #                         print(f'Current Position: x={odom.position.x}, y={odom.position.y}, z={odom.position.z}')


    #                     # current_pose=self.agent.navigator.get_current_pose()

    #                     # try:
    #                     #     # Get the transform from 'map' to 'base_link' frames
    #                     #     transform: TransformStamped = self.tf_buffer.lookup_transform(
    #                     #         'map', 'base_link', rclpy.time.Time())
                            
    #                     #     # Extract translation (x, y)
    #                     #     x = transform.transform.translation.x
    #                     #     y = transform.transform.translation.y

    #                     #     # Extract rotation (yaw angle)
    #                     #     orientation_q = transform.transform.rotation
    #                     #     (_, _, yaw) = euler_from_quaternion([
    #                     #         orientation_q.x,
    #                     #         orientation_q.y,
    #                     #         orientation_q.z,
    #                     #         orientation_q.w])
    #                     #     self.agent.amr_breakdown_coordinates=[x,y]

    #                     #     self.get_logger().info(f"Robot Position: x={x}, y={y}, yaw={yaw}")

    #                     # except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
    #                     #     self.get_logger().warn("Transform not available")

    #                 else:
    #                     print("No Breakdown")

    #             else:
    #                 print("No MSG")


    #         elif self.agent.breakdown==True:
    #             print("State: Breakdown. Sending JID of assistance agent...")
    #             msg = Message(to="scheduler@jabber.fr")
    #             msg.set_metadata("performative", "Breakdown: please assist")
    #             msg.body = str(self.agent.amr_breakdown_coordinates)
    #             await self.send(msg)
    #             print("Breakdown message sent to scheduler agent.")
    #             msg1 = await self.receive(timeout=30)
    #             if msg1:
    #                 # self.agent.sender_jid =self.agent.RAmrAgents[msg.sender.bare]
    #                 if msg1.get_metadata("performative") == "ask" and msg1.body == "send jobs yet to processed":
    #                     msg2 = Message(to="scheduler@jabber.fr")
    #                     msg2.set_metadata("performative", "jobs")
    #                     msg2.body = str(self.agent.amr_breakdown_coordinates)
    #                     await self.send(msg2)
                        
                    


    class Dock(State):
        async def run(self):
            print("In Dock")
            if self.agent.dock==False:
                self.agent.machine='22'
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

        self.navigator = BasicNavigator(namespace="robot2")
        # self.odom_sub=OdomSubscriber()

        # self.timer = self.odom_sub.create_timer(1.0, self.get_robot_position)

        # self.tf_buffer = tf2_ros.Buffer()
        # self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self.odom_sub)

        # spin the odom node
        # self.odom_sub.spin_in_background()
        
        fsm = self.AMRFSM()
        #All the States
        fsm.add_state(name="Ready", state=self.Ready(), initial=True)
        fsm.add_state(name="waitingfor_jobset", state=self.waitingfor_jobset())
        fsm.add_state(name="wait_for_newjobs", state=self.wait_for_newjobs())
        fsm.add_state(name="loading", state=self.Loading())
        fsm.add_state(name="unloading", state=self.Unloading())
        fsm.add_state(name="Idle", state=self.Idle())
        fsm.add_state(name="Dock", state=self.Dock())
        fsm.add_state(name="Processing", state=self.Processing())
        # fsm.add_state(name="Breakdown", state=self.Breakdown())

        # Transition from one State to another State
        fsm.add_transition(source="Ready", dest="Ready")
        fsm.add_transition(source="waitingfor_jobset", dest="Ready")
        fsm.add_transition(source="Ready", dest="waitingfor_jobset")

        fsm.add_transition(source="waitingfor_jobset", dest="waitingfor_jobset")
        fsm.add_transition(source="waitingfor_jobset", dest="wait_for_newjobs")
        fsm.add_transition(source="wait_for_newjobs", dest="wait_for_newjobs")
        fsm.add_transition(source="wait_for_newjobs", dest="Idle")
        fsm.add_transition(source="waitingfor_jobset", dest="loading")

        fsm.add_transition(source="loading", dest="loading")
        fsm.add_transition(source="Processing", dest="loading")
        fsm.add_transition(source="loading", dest="Processing")
        fsm.add_transition(source="loading", dest="Idle")

        fsm.add_transition(source="Idle", dest="Idle")
        fsm.add_transition(source="Idle", dest="Processing")
        fsm.add_transition(source="Processing", dest="Idle")

        # fsm.add_transition(source="Idle", dest="Breakdown")
        # fsm.add_transition(source="Breakdown", dest="Idle")
        # fsm.add_transition(source="Processing", dest="Breakdown")

        fsm.add_transition(source="Processing", dest="unloading")
        fsm.add_transition(source="unloading", dest="Processing")
        fsm.add_transition(source="unloading", dest="Dock")
        fsm.add_transition(source="unloading", dest="loading")
        fsm.add_transition(source="unloading", dest="unloading")
        fsm.add_transition(source="Idle", dest="unloading")

        fsm.add_transition(source="Idle", dest="Dock")
        fsm.add_transition(source="Dock", dest="Idle")
        fsm.add_transition(source="Dock", dest="Processing")
        fsm.add_transition(source="Dock", dest="Dock")
        fsm.add_transition(source="Dock", dest="Ready")

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
        # amr2.web.start(hostname="127.0.0.1", port="10001")
        print("AMR2 started")

        try:
            while amr2.is_alive():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await amr2.stop()

    asyncio.run(run())