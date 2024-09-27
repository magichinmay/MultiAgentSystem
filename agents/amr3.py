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

class AMR3(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class AMRFSM(FSMBehaviour):
        async def on_start(self):
            print("AMR3 FSM started.")

        async def on_end(self):
            print("AMR3 FSM finished.")

    class Ready(State):
        async def run(self):
            print("AMR3 is Ready")
            register = Message(to="scheduler@jabber.fr")
            register.set_metadata("performative", "Register")
            register.body = "robot3@jabber.fr"
            await self.send(register)  # Sending the register message
            await asyncio.sleep(2)
            msg1 = await self.receive(timeout=5)
            if msg1:
                performative = msg1.get_metadata("performative")
                if performative == "inform" and msg1.body == "Registered":
                    print("Successfully Registered")
            self.set_next_state("Idle")

    class Idle(State):
        async def run(self):
            reply = Message(to="scheduler@jabber.fr")
            reply.set_metadata("performative", "robot3@jabber.fr")
            reply.body = "Idle"
            await self.send(reply)
            print("Sent Idle status to SchedulerAgent.")
            await asyncio.sleep(1)
            msg = await self.receive(timeout=10)
            if msg:
                performative = msg.get_metadata("performative")
                if performative == "order":
                    try:
                        data2 = json.loads(msg.body)
                        machine=data2[0]
                        ptime=data2[1]
                        if isinstance(machine, int):
                            print(f"Received coordinates: {machine}")
                            self.agent.machine = machine
                            self.agent.ptime = ptime
                            self.set_next_state("Processing")
                        else:
                            print("Error: Received data is not a valid coordinate.")
                            self.set_next_state("Idle")
                    except json.JSONDecodeError:
                        print("Error: Unable to decode message body as JSON.")
                        self.set_next_state("Idle")

                elif performative == "user_input" and msg.body == "breakdown":
                    self.set_next_state("Breakdown")

                elif performative=="inform" and msg.body=="AMR3 tasks are done":
                    self.set_next_state("Dock")

            else:
                print("No Message Received")
                self.set_next_state("Idle")

    class Processing(State):
        async def run(self):
            print(f"State: Processing coordinates: {self.agent.machine}")
            print(f"State: Processing Time: {self.agent.ptime}")
            
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
                print(f"Going to Machine: {self.agent.machine}")
                await asyncio.sleep(self.agent.ptime)  # Simulate processing for 5 seconds
                print(f"Machine finished processing")
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
            msg.set_metadata("performative", "inform")
            msg.body = "Breakdown: please assist."
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
        fsm.add_state(name="Idle", state=self.Idle())
        fsm.add_state(name="Dock", state=self.Dock())
        fsm.add_state(name="Processing", state=self.Processing())
        fsm.add_state(name="breakdown", state=self.Breakdown())

        # Transition from one State to another State
        fsm.add_transition(source="Ready", dest="Idle")
        fsm.add_transition(source="Idle", dest="Processing")
        fsm.add_transition(source="Processing", dest="Idle")
        fsm.add_transition(source="Idle", dest="breakdown")
        fsm.add_transition(source="breakdown", dest="Idle")
        fsm.add_transition(source="Processing", dest="breakdown")
        fsm.add_transition(source="Idle", dest="Idle")
        fsm.add_transition(source="Idle", dest="Dock")
        fsm.add_transition(source="Dock", dest="Idle")

        self.add_behaviour(fsm)

        # Register handlers for XMPP version and disco queries
        self.presence.version_handler = self.version_query_handler
        self.presence.disco_info_handler = self.disco_info_query_handler

    def version_query_handler(self, iq):
        iq.make_result()
        version_data = version.xso.Query()
        version_data.name = "AMR3"
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
