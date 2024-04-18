from agent import Agent
import constants
import model_info
import numpy as np

from general_maths import calculate_distance
from points import Point
from base import Harbour

import os
import logging
import datetime

date = datetime.date.today()
logging.basicConfig(level=logging.DEBUG, filename=os.path.join(os.getcwd(), 'logs/navy_log_' + str(date) + '.log'),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt="%H:%M:%S")
logger = logging.getLogger("SUBMARINE")
logger.setLevel(logging.WARNING)

submarine_id = 0


class SubTube:
    def __init__(self):
        self.time_last_shot = 0
        self.reload_time = constants.TUBE_RELOAD_TIME

    def armed(self) -> bool:
        if self.time_last_shot + self.reload_time > constants.world.world_time:
            return False
        else:
            return True

    def tube_launched_attack(self, target):
        """
        Updates tube to "fired state".
        :return:
        """
        if not self.armed():
            raise ValueError(f"Attempting to launch unarmed tube")

        self.time_last_shot = constants.world.world_time
        if np.random.uniform(0, 1) < 0.7:
            # Missile hit the target
            # TODO: damage calculations on target agent
            pass


class Submarine(Agent):
    def __init__(self, team: int, base: Harbour, obstacles: list, color: str, model: str):
        super().__init__(team, base, obstacles, color)
        global submarine_id
        self.sub_id = submarine_id
        submarine_id += 1

        self.model = model
        self.mission = None

        # ---- Model Properties -----
        self.sub_type = None
        self.visibility = None
        self.battery_max = None
        self.battery_current = None
        self.endurance = None
        self.surface_detect_range = None
        self.num_tubes = None
        self.tubes = None
        self.num_attacks = None
        self.num_in_OOB = None
        self.initiate_model_parameters()

        self.missiles_ammunition = None
        self.torpedo_ammunition = None

        # ---- Sub Specific Status ----
        self.entry_point = None
        self.snorkeling = False
        self.time_since_last_fired = 0

    def initiate_model_parameters(self):
        for blueprint in model_info.SUBMARINE_MODELS:
            if self.model == blueprint['name']:
                self.sub_type = blueprint['type']

                if self.sub_type == "Diesel" or self.sub_type == "AIP":
                    self.battery_max = 700
                    self.battery_current = self.battery_max

                self.visibility = blueprint['visibility']
                self.endurance = blueprint['endurance']
                self.surface_detect_range = blueprint['SDR']
                self.num_tubes = blueprint['num_tubes']
                self.tubes = [SubTube() for _ in range(self.num_tubes)]
                self.max_ammunition = blueprint['max_ammunition']
                self.num_in_OOB = blueprint['num_OOB']
                return

    def activate(self, mission=None):
        """
        Activates stationed submarine to start a mission.
        :type mission: Either "TEL" or "Searching"
        """
        self.stationed = False
        self.mission = mission

        if self.mission == "TEL":
            self.missiles_ammunition = int(np.floor(self.max_ammunition * 2 / 3))
            self.torpedo_ammunition = self.max_ammunition - self.missiles_ammunition
        elif self.mission == "Searching":
            self.missiles_ammunition = 0
            self.torpedo_ammunition = self.max_ammunition
            self.speed = 12
        else:
            return NotImplementedError(f"Mission type {mission} activation is not implemented for Submarines!")

    def move(self, distance_to_travel=None):
        if distance_to_travel is not None:
            self.distance_to_travel = distance_to_travel

        while distance_to_travel > 0:
            if self.trailing:
                self.move_through_route()
                if self.able_to_attack:
                    self.engage_agent()
                else:
                    return

            if self.mission == "Searching":
                # TODO: Add movement in patrol area
                pass
            elif self.mission == "TEL":
                self.update_battery_level()

    def engage_agent(self):

        if self.mission == "TEL":
            #
            self.stop_snorkeling()
            for _ in range(constants.NUM_MISSILES_TO_LAUNCH):
                self.launch_missile(self.located_agent)

            self.visibility += 1

            available_tubes = [tube for tube in self.tubes if tube.armed()]
            other_targets = []
            if len(available_tubes) == 0:
                self.start_retreat()
            elif len(other_targets) > 0:
                # TODO: attack other targets (till fix selection of other targets) - also allow to await for reload
                pass
            else:
                self.start_retreat()

        pass

    def launch_missile(self, agent):
        """
        Launch missile at agent
        :param agent:
        :return:
        """
        available_tubes = [tube for tube in self.tubes if tube.armed()]
        if len(available_tubes) == 0:
            raise ValueError(f"No tubes available")
        else:
            available_tubes[0].tube_launched_attack(self.located_agent)

    def generate_entry_point(self):
        if np.random.rand() < 2 / 3:
            y = constants.MIN_LONG
        else:
            # Generate entry point North
            y = constants.MAX_LONG

        while True:
            lamb = np.random.random()
            entry_point = Point(x=lamb * constants.MAX_LAT + (1 - lamb) *
                                  (0.5 * constants.MIN_LAT + 0.5 * constants.MAX_LAT),
                                y=y)
            in_landmass = any([landmass.check_if_contains_point(entry_point)
                               for landmass in constants.world.landmasses])
            if not in_landmass:
                break

        self.entry_point = entry_point

    def observe_area(self):
        active_hostile_agents = [agent
                                 for manager in constants.world.managers
                                 for agent in manager.agents
                                 if agent.team != self.team and not agent.left_world]
        for agent in active_hostile_agents:
            radius_travelled = self.radius + self.speed * constants.world.time_delta

            if calculate_distance(a=self.location, b=agent.location) > radius_travelled:
                continue

            for lamb in np.append(np.arange(0, 1, step=1 / constants.world.splits_per_step), 1):
                own_location = Point(self.location.x * lamb + self.last_location.x * (1 - lamb),
                                     self.location.y * lamb + self.last_location.y * (1 - lamb))
                distance = calculate_distance(a=own_location, b=agent.location)

                if distance < 9:
                    self.assign_target(agent)
                # TODO: Check if surface detect range is "filled circle" or a "donut"
                elif self.surface_detect_range - 5 <= distance <= self.surface_detect_range + 5:
                    self.assign_target(agent)

    def assign_target(self, agent):
        """
        Assigns a target to the submarine, either by 3rd party detection or own detection
        :param agent:
        :return:
        """
        self.trailing = True
        self.located_agent = agent
        agent.trailing_agents.append(self)

    def check_if_start_snorkeling(self):
        if self.sub_type == "Nuke":
            return

        if self.battery_current < self.battery_max / 2:
            self.start_snorkeling()

    def update_battery_level(self, distance_travelled: int=None):
        if self.sub_type == "Diesel":
            if self.mission == "TEL":
                self.battery_current = self.battery_current - (constants.world.time_delta * 10)
            elif self.mission == "Searching":
                self.battery_current = self.battery_current - distance_travelled
            else:
                raise NotImplementedError(f"NO BATTERY DRAINING METHOD FOR MISSION {self.mission}")
        elif self.sub_type == "AIP":

            if self.mission == "TEL":
                self.battery_current = self.battery_current - (constants.world.time_delta * 10)

    def start_snorkeling(self):
        self.snorkeling = True
        self.visibility -= 1

    def stop_snorkeling(self):
        self.snorkeling = False
        self.visibility += 1

