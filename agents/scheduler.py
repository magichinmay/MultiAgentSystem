from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import asyncio
import json
import sys
import os

sys.path.insert(1, "/home/ubantu/mas_ws/src/MultiAgentSystem/JobShopGA")
from JobShopScheduler import JobShopScheduler
import benchmarks
import distances

class SchedulerAgent(Agent):
    def __init__(self, jid, password):
        # Pass the jid and password to the parent Agent class
        super().__init__(jid, password)
        
        # Initialize JobShopScheduler
        machine_data = benchmarks.pinedo['machine_data']
        ptime_data = benchmarks.pinedo['ptime_data']
        amrs=2
        scheduler1 = JobShopScheduler(4, 3, amrs, 50, 0.7, 0.5, 100, machine_data, ptime_data)
        scheduler1.display_schedule = 0
        chromsome1 = scheduler1.GeneticAlgorithm()
        scheduler1.num_amrs = 2
        print("Machine Sequnce",chromsome1.amr_machine_sequences)
        # print(scheduler1)
        # Set up agent-specific attributes
        self.coordinates1 = chromsome1.amr_machine_sequences[0]  # Example list of coordinates
        self.coordinates2 = chromsome1.amr_machine_sequences[1]
        self.index1 = 0  # Keep track of which coordinate to send
        self.index2 = 0 
        self.waiting_for_idle = False  # Flag to track waiting for idle response1
        self.current_state1 = "waiting for schedule"
        self.current_state2 = "waiting for schedule"
        

    class SchedulerBehaviour(CyclicBehaviour):
        async def run(self):
            print("scheduler waiting robots to register")
            self.robots = []
            msg = await self.receive(timeout=15)
            if msg:
                print(msg.body)
                performative = msg.get_metadata("performative")
                if performative == "Register":
                    self.agent.robots.append(msg.body)
                    print(msg.body,"successfully registered")

                elif performative == "robot2@jabber.fr" and msg.body=="Idle":
                    # AMR1 is idle, send the next coordinate
                    point1 = self.agent.coordinates1[self.agent.index1]  # Access agent's coordinates
                    msg = Message(to="robot2@jabber.fr")  # JID of the AMR1 agent
                    msg.set_metadata("performative", "order")
                    msg.body = json.dumps(point1)  # Convert the coordinate to JSON string
                    await self.send(msg)
                    print(f"Sending coordinate: {point1} to AMR2")
                    # Update index for next coordinate
                    self.agent.index1 = (self.agent.index1 + 1) % len(self.agent.coordinates1)
                    await asyncio.sleep(5)  # Wait before sending the next point

                elif performative == "robot3@jabber.fr" and msg.body=="Idle":
                    # AMR1 is idle, send the next coordinate
                    point2 = self.agent.coordinates2[self.agent.index2]  # Access agent's coordinates
                    msg = Message(to="robot3@jabber.fr")  # JID of the AMR1 agent
                    msg.set_metadata("performative", "order")
                    msg.body = json.dumps(point2)  # Convert the coordinate to JSON string
                    await self.send(msg)
                    print(f"Sending coordinate: {point2} to AMR3")
                    # Update index for next coordinate
                    self.agent.index2 = (self.agent.index2 + 1) % len(self.agent.coordinates2)
                    await asyncio.sleep(5)  # Wait before sending the next point

                else:
                    print("AMR1 is not in Idle state, retrying...")
                    self.agent.waiting_for_idle = False  # Reset the agent's attribute

            else:
                print("No response1 from AMR1, will retry after some time.")
                await asyncio.sleep(5)  # Wait before checking again

    async def setup(self):
        scheduler_behaviour = self.SchedulerBehaviour()
        self.add_behaviour(scheduler_behaviour)

if __name__ == "__main__":
    # Provide JID and password for the agent
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
