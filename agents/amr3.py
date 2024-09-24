from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message
import asyncio
import json

import time
from copy import deepcopy

from geometry_msgs.msg import PoseStamped
from rclpy.duration import Duration
import rclpy
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult



class AMR3(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.current_state = "Ready" 

    class AMRFSM(FSMBehaviour):
        async def on_start(self):
            print("AMR3 FSM started.")


        async def on_end(self):
            print("AMR3 FSM finished.")
            
    class Ready(State):
         async def run(self):
            print("AMR3 is Ready")
            register=Message(to="scheduler@jabber.fr")
            register.set_metadata("performative","Register")
            register.body="robot3@jabber.fr"
            print("registered")
            await asyncio.sleep(2)
            self.set_next_state("Idle")
        


    class Idle(State):
        async def run(self):

            reply = Message(to="scheduler@jabber.fr")  # Convert sender to string explicitly
            reply.set_metadata("performative", "robot3@jabber.fr")
            reply.body = "Idle"
            await self.send(reply)
            print("Sent Idle status to SchedulerAgent.")
            await asyncio.sleep(1)
            msg = await self.receive(timeout=10)  # Wait for a message with a 10-second timeout
            if msg:
                performative = msg.get_metadata("performative")
                if performative=="order":
                    try:
                        machine = json.loads(msg.body)  # Deserialize the received JSON message
                        if isinstance(machine, int):  # Ensure it's a valid coordinate
                            print(f"Received coordinates: {machine}")
                            self.agent.machine = machine  # Store coordinates for later processing
                            self.agent.current_state="Processing"
                            self.set_next_state("Processing")
                        else:
                            print("Error: Received data is not a valid coordinate.")
                            self.set_next_state("Idle")
                    except json.JSONDecodeError:
                        print("Error: Unable to decode message body as JSON.")
                        self.set_next_state("Idle")

                elif performative=="user_input" and msg.body == "breakdown":
                    self.set_next_state("Breakdown")
            else:
                print("No Message Received")
                self.set_next_state("Idle")



    class Processing(State):
        async def run(self):
            print(f"State: Processing. Processing coordinates: {self.agent.machine}")
            await asyncio.sleep(5)
            self.set_next_state("Idle")
            # rclpy.init()
            # pose=self.agent.machine
            # navigator = BasicNavigator()

            # m1 = [-3.32, 6.65]
            # m2 = [-3.38, 1.46]
            # m3 = [1.627, 6.459]
            # m4 = [1.681, 1.407]
            # loading_dock = [-6.69, 4.028]
            # unloading_dock = [3.52, 3.96]

            # poses = {
            #     '0': m1,
            #     '1': m2,
            #     '2': m3,
            #     '3': m4,
            #     '-1': loading_dock,
            #     '-2': unloading_dock
            # }

            # goal_pose = PoseStamped()
            # goal_pose.header.frame_id = 'map'
            # goal_pose.header.stamp = navigator.get_clock().now().to_msg()
            # goal_pose.pose.position.x = poses[str(pose)][0]
            # goal_pose.pose.position.y = poses[str(pose)][1] 
            # goal_pose.pose.orientation.w = 1.0

            # navigator.goToPose(goal_pose)

            # result = navigator.getResult()
            # if result == TaskResult.SUCCEEDED:
            #     print(f"Going to Machine: {self.agent.machine}")
            #     await asyncio.sleep(5)  # Simulate processing for 5 seconds
            #     print(f"Machine finished processing")
            #     self.set_next_state("Idle")  # Return to Idle after processing
            # elif result == TaskResult.CANCELED:
            #     print('Inspection of shelving was canceled. Returning to start...')
            #     exit(1)
            # elif result == TaskResult.FAILED:
            #     print('Inspection of shelving failed! Returning to start...')

            

    class Breakdown(State):
        async def run(self):
            print("State: Breakdown. Sending JID of assistance agent...")
            msg = Message(to="scheduler@jabber.fr")  # JID of another agent
            msg.set_metadata("performative", "inform")
            msg.body = "Breakdown: please assist."
            
            await self.send(msg)
            print("Breakdown message sent to another agent.")
            # self.set_next_state("Idle")  # Go back to Idle state after breakdown



    async def setup(self):
        # Initialize FSM
        fsm = self.AMRFSM()

        # Add states to FSM
        fsm.add_state(name="Ready", state=self.Ready(), initial=True)
        fsm.add_state(name="Idle", state=self.Idle())
        fsm.add_state(name="Processing", state=self.Processing())
        fsm.add_state(name="breakdown", state=self.Breakdown())


        # Define transitions between states
        fsm.add_transition(source="Ready", dest="Idle")
        fsm.add_transition(source="Idle", dest="Processing")
        fsm.add_transition(source="breakdown", dest="Processing")
        fsm.add_transition(source="Idle", dest="breakdown")
        fsm.add_transition(source="Processing", dest="Idle")
        fsm.add_transition(source="Processing", dest="breakdown")
        fsm.add_transition(source="breakdown", dest="Idle")
        fsm.add_transition(source="Idle", dest="Idle")


        # Add FSM to the agent
        self.add_behaviour(fsm)

if __name__ == "__main__":
    amr3 = AMR3("robot3@jabber.fr", "changeme")

    async def run():
        await amr3.start()
        print("AMR3 started")

        try:
            while amr3.is_alive():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await amr3.stop()

    asyncio.run(run())
