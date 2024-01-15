from ships import TaiwanEscort, Merchant
from drones import Drone

import numpy as np
import constants

class Manager:
    """
    A manager ensures that their designated subset of agents work together as intended.
    This includes ensuring the resources are spread out over time.
    Managers can also communicate with each other, but this can cause delays.
    """
    def __init__(self):
        self.agents = []
        self.bases = []

        self.utilization_rates = {}


class TaiwanEscortManager(Manager):
    def __init__(self):
        super().__init__()

        self.initiate_docks()
        self.initiate_escorts()

    def initiate_docks(self):
        pass

    def initiate_escorts(self):
        self.agents = [TaiwanEscort(name="Test Escort",
                                    model="Zhaotou",
                                    base=self.select_random_harbour(),
                                    obstacles=constants.world.polygons)]

    def select_random_harbour(self):
        return np.random.choice(self.bases)
