from agent import Agent
import constants
import model_info
import numpy as np

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
        self.loaded_tubes = None
        self.num_attacks = None
        self.num_in_OOB = None

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
        else:
            return NotImplementedError(f"Mission type {mission} activation is not implemented for Submarines!")

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

    def check_if_start_snorkeling(self):
        if self.sub_type == "Nuke":
            return

        if self.battery_current < self.battery_max / 2:
            self.start_snorkeling()

    def update_battery_level(self):
        if self.sub_type == "Diesel":

            if self.mission == "TEL":
                self.battery_current = self.battery_current - (constants.world.time_delta * 10)
            else:
                raise NotImplementedError(f"NO BATTERY DRAINING METHOD FOR MISSION {self.mission}")
        elif self.sub_type == "AIP":

            if self.mission == "TEL":
                self.battery_current = self.battery_current - (constants.world.time_delta * 10)

    def start_snorkeling(self):
        self.snorkeling = True
        self.visibility += 1

    def stop_snorkeling(self):
        self.snorkeling = False
        self.visibility -= 1

