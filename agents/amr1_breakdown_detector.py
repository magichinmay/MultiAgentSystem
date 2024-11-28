import asyncio
import spade
from spade import wait_until_finished
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour,FSMBehaviour, State
from spade.message import Message
import json
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry

if not rclpy.ok():  # Ensure rclpy.init() is called only once
    rclpy.init()

class OdomSubscriber(Node):

    def __init__(self):
        super().__init__('odom_subscriber')
        # Subscribe to the /odom topic
        self.subscription = self.create_subscription(
            Odometry,
            '/robot1/odom',  # Topic name
            self.odom_callback,  # Callback function
            10  # QoS profile, 10 is a common choice
        )
        self.subscription  # Prevents the subscription from being garbage collected
        
        # Store the latest odometry data
        self.current_odom = None

    def odom_callback(self, msg):
        # Update the current odometry with the latest message
        self.current_odom = msg
        # position = msg.pose.pose.position
        # orientation = msg.pose.pose.orientation
        # self.get_logger().info(f"Position: x={position.x}, y={position.y}, z={position.z}")
        # self.get_logger().info(f"Orientation: x={orientation.x}, y={orientation.y}, z={orientation.z}, w={orientation.w}")

    def get_current_odom(self):
        # Function to return the latest stored odometry data
        if self.current_odom:
            return self.current_odom.pose.pose
        else:
            return None

class BreakdownDetector(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.counter = 0

    class AMR_Breakdown_Detect_FSM(FSMBehaviour):
        async def on_start(self):
            print("AMR1 Breakdown Detector FSM started.")

        async def on_end(self):
            print("AMR1 Breakdown Detector FSM finished.")

    class GetLocation(State):
        async def run(self):
            print("waiting for amr request")
            ask1=await self.receive(timeout=30)
            if ask1:
                if ask1.get_metadata("performative") == "ask_breakdown_detector" and ask1.body=="my_coordinates" :
                    try:
                        if rclpy.ok():
                            rclpy.spin_once(self.agent.odom_sub)
                            
                            # Access the current odom data when needed
                            odom = self.agent.odom_sub.get_current_odom()
                            if odom:
                                print(f'Current Position: x={odom.position.x}, y={odom.position.y}, z={odom.position.z}')
                                print(f'Orientation: x={odom.orientation.x}, y={odom.orientation.y}, z={odom.orientation.z}, w={odom.orientation.w}')
                    
                    except KeyboardInterrupt:
                        pass
                    finally:
                        # Clean up when the script is stopped
                        self.agent.odom_sub.destroy_node()
                        rclpy.shutdown()
   
                    tell=Message(to=str(ask1.sender))
                    tell.set_metadata("performative", "amr_coordinates")
                    tell.body = json.dumps(odom)
                    print(tell.body)
                    await self.send(tell)
                else:
                     self.set_next_state("GetLocation")           
            else:
                self.set_next_state("GetLocation")


    async def setup(self):
        print("Agent starting . . .")

        fsm=self.AMR_Breakdown_Detect_FSM()

        fsm.add_state(name="GetLocation", state=self.GetLocation(), initial=True)

        fsm.add_transition(source="GetLocation", dest="GetLocation")

        self.odom_sub = OdomSubscriber()
        # self.odom_sub.spin_in_background()
        # b = self.GetLocation()
        self.add_behaviour(fsm)

if __name__ == "__main__":
    agent = BreakdownDetector("amr1_breakdown_detector@jabber.fr", "changeme")

    async def run():
        await agent.start()
        # agent.web.start(hostname="127.0.0.1", port="10001")
        print("amr1_breakdown_detector started")

        try:
            while agent.is_alive():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await agent.stop()

    asyncio.run(run())