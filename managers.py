from agent import Agent
from ships import TaiwanEscort, Merchant
from base import Harbour, Airbase
from drones import Drone, DroneType

from points import Point

import model_info
import constants

import random
import numpy as np

import os
import logging
import datetime

date = datetime.date.today()
logging.basicConfig(level=logging.DEBUG, filename=os.path.join(os.getcwd(), 'logs/navy_log_' + str(date) + '.log'),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt="%H:%M:%S")
logger = logging.getLogger("MANAGERS")
logger.setLevel(logging.DEBUG)


class AgentManager:
    """
    A manager ensures that their designated subset of agents work together as intended.
    This includes ensuring the resources are spread out over time.
    Managers can also communicate with each other, but this can cause delays.
    """

    def __init__(self):
        self.agents = []
        self.destroyed_agents = []
        self.bases = []

        self.utilization_rates = {}

    def initiate_agents(self):
        raise NotImplementedError("Initiate Agents not defined on MANAGER Level")

    def initiate_bases(self):
        raise NotImplementedError("Initiate Bases not defined on MANAGER Level")

    def calculate_utilization_rates(self):
        """
        To be called after initializing agents and bases to calculate the utilization rates for the different models.
        Saves the results in a dictionary with the models as keys.
        :return:
        """
        models = set([agent.model for agent in self.agents])

        for model in models:
            agent_of_model = [agent for agent in self.agents if agent.model == model][0]
            min_time_to_trail = 0.5
            min_time_to_travel = 600 / agent_of_model.speed
            self.utilization_rates[model] = 0.5 * (
                    (agent_of_model.endurance - (2 * min_time_to_travel + min_time_to_trail)) /
                    (agent_of_model.endurance + agent_of_model.maintenance_time))

    def custom_actions(self):
        """
        Module that can be overwritten for subclasses to perform unique actions before managing agents.
        :return:
        """
        pass

    def manage_agents(self):
        logger.debug(f"{self} performing custom actions")
        self.custom_actions()

        logger.debug(f"{self} serving agents")
        for base in self.bases:
            base.serve_agents()

        # Check if the agent has been destroyed
        logger.debug(f"{self} checking destroyed agents")
        active_agents = [agent for agent in self.agents if not agent.stationed]
        for agent in active_agents:
            if agent.destroyed:
                self.agents.remove(agent)
                self.destroyed_agents.append(agent)

        # Check if agent needs to return for resupply
        logger.debug(f"{self} checking if agents require resupplying")
        active_agents = [agent for agent in self.agents if not agent.stationed]
        for agent in active_agents:
            if isinstance(agent, Merchant):
                # Merchants don't have a limit on endurance, so we skip those
                continue

            distances_to_bases = []
            for base in self.bases:
                distances_to_bases.append([agent.location.distance_to_point(base.location), base])

            distance_to_resupply, base = min(distances_to_bases, key=lambda x: x[0])
            remaining_endurance = agent.endurance - agent.time_spent_from_base

            if agent.speed is None:
                raise ValueError(f"Agent {agent} speed is None")
            if distance_to_resupply is None:
                raise ValueError(f"Distance to resupply is {distance_to_resupply}")

            if remaining_endurance < (distance_to_resupply / agent.speed) * constants.SAFETY_ENDURANCE:
                agent.go_resupply(base)

        # Check if utilization is satisfied - if not, send out new agents if feasible
        logger.debug(f"{self} checking if we are able to send out more agents")
        for model in set([agent.model for agent in self.agents]):
            agents_of_model = [agent for agent in self.agents if agent.model == model]
            active_agents = [agent for agent in agents_of_model if not agent.stationed]
            current_utilization = len(active_agents) / len(agents_of_model)
            available_inactive_agents = [agent for agent in agents_of_model
                                         if agent.remaining_maintenance_time == 0
                                         and agent.stationed]

            # TODO: OPTIONAL See if we can launch more than one per timestep?
            #  - maybe depending on length of timestep?
            while current_utilization < self.utilization_rates[model] and len(available_inactive_agents) > 0:
                ready_agent = np.random.choice(available_inactive_agents)
                ready_agent.activate()

                available_inactive_agents = [agent for agent in agents_of_model
                                             if agent.remaining_maintenance_time == 0
                                             and agent.stationed]
                current_utilization = (len(agents_of_model) - len(available_inactive_agents)) / len(agents_of_model)

        # Make agent moves
        logger.debug(f"{self} making agent moves")
        for agent in [agent for agent in self.agents if not agent.stationed]:
            agent.make_move()

    def select_random_base(self):
        return np.random.choice(self.bases)


class UAVManager(AgentManager):
    """
    Chinese UAV Manager
    """

    def __init__(self):
        super().__init__()

        self.drone_types = []

        self.initiate_bases()
        self.initiate_drones()
        self.calculate_utilization_rates()

    def __str__(self):
        return "UAV Agent Manager"

    def initiate_bases(self):
        self.bases = [Airbase(name="Ningbo", location=Point(121.57, 29.92,
                                                            force_maintain=True, name="Ningbo")),
                      Airbase(name="Fuzhou", location=Point(119.31, 26.00,
                                                            force_maintain=True, name="Fuzhou")),
                      Airbase(name="Liangcheng", location=Point(116.75, 25.68,
                                                                force_maintain=True, name="Liangcheng")),
                      ]

    def initiate_drones(self):
        # TODO: Distribute drones equally over airbases
        logger.debug("Initiating Drones...")

        for model in model_info.UAV_MODELS:
            drone_type = DroneType(model=model['name'],
                                   amount=np.floor(model['number_of_airframes'] * constants.UAV_AVAILABILITY))
            self.drone_types.append(drone_type)

            for _ in range(int(np.floor(model['number_of_airframes'] * constants.UAV_AVAILABILITY))):
                new_drone = Drone(model=model['name'], drone_type=drone_type,
                                  base=np.random.choice(self.bases), obstacles=constants.world.landmasses)
                self.agents.append(new_drone)
                drone_type.drones.append(new_drone)

            drone_type.calculate_utilization_rate()


class MerchantManager(AgentManager):
    """
    Manager for all 'neutral' Merchants
    """

    def __init__(self):
        super().__init__()
        self.initiate_bases()

    def __str__(self):
        return "Merchant Manager"

    def initiate_bases(self) -> None:
        self.bases = [Harbour(name="Kaohsiung",
                              location=Point(120.30, 22.44, name="Kaohsiung", force_maintain=True),
                              probability=0.4),
                      Harbour(name="Tiachung",
                              location=Point(120.42, 24.21, name="Tiachung", force_maintain=True),
                              probability=0.3),
                      Harbour(name="Keelung",
                              location=Point(121.75, 25.19, name="Keelung", force_maintain=True),
                              probability=0.25),
                      Harbour(name="Hualien",
                              location=Point(121.70, 23.96, name="Hualien", force_maintain=True),
                              probability=0.05)
                      ]

    def select_random_base(self) -> Harbour:
        if len(self.bases) == 0:
            raise ValueError("No list of bases available to select from")
        else:
            return random.choices(self.bases, weights=[base.probability
                                                       if base.probability is not None else 1 / len(self.bases)
                                                       for base in self.bases], k=1)[0]

    def generate_new_merchant(self) -> None:
        model = random.choices(["Cargo", "Container", "Bulk"],
                               weights=[constants.CARGO_DAILY_ARRIVAL_MEAN,
                                        constants.BULK_DAILY_ARRIVAL_MEAN,
                                        constants.CONTAINER_DAILY_ARRIVAL_MEAN], k=1)[0]
        base = self.select_random_base()
        new_merchant = Merchant(model, base, obstacles=constants.world.landmasses)
        self.agents.append(new_merchant)
        new_merchant.enter_world()

    @staticmethod
    def calculate_ships_entering() -> int:
        """
        Calculate number of ships entering in time period t.
        :return: Integer number of ships entering
        """
        # TODO: Sample from poisson with rate lambda as in overleaf
        if np.random.rand() > 0.98:
            return 1
        else:
            return 0

    def custom_actions(self) -> None:
        for _ in range(self.calculate_ships_entering()):
            self.generate_new_merchant()

    def manage_agents(self):
        logger.debug(f"{self} performing custom actions...")
        self.custom_actions()

        logger.debug(f"{self} serving agents...")
        for base in self.bases:
            base.serve_agents()

        # Check if the agent has been destroyed
        logger.debug(f"{self} checking for destroyed agents...")
        active_agents = [agent for agent in self.agents if not agent.stationed]
        for agent in active_agents:
            if agent.destroyed:
                self.agents.remove(agent)
                self.destroyed_agents.append(agent)

        # Make agent moves
        logger.debug(f"{self} making moves...")
        for agent in [agent for agent in self.agents if not agent.stationed and not agent.destroyed]:
            agent.make_move()


class USManager(AgentManager):
    """
    Manager for all US Agents
    """

    def __init__(self):
        super().__init__()

        self.initiate_bases()
        self.initiate_agents()

        self.calculate_utilization_rates()

    def __str__(self):
        return "US Agent Manager"

    def initiate_bases(self) -> None:
        self.bases = [Harbour(name="US Oiler", location=Point(150, 25.88))]

    def initiate_agents(self) -> None:
        pass


class TaiwanManager(AgentManager):
    """
    Manager for all Taiwanese Agents
    """

    def __init__(self):
        super().__init__()

        self.initiate_bases()
        self.initiate_agents()

        self.calculate_utilization_rates()

    def __str__(self):
        return "Taiwan Agent Manager"

    def initiate_bases(self) -> None:
        self.bases = [Harbour(name="Haulien", location=Point(121.67, 23.97, name="Haulien Port"))]

    def initiate_agents(self) -> None:
        self.agents = [TaiwanEscort(model="Zhaotou",
                                    base=self.select_random_base(),
                                    obstacles=constants.world.landmasses)]


class JapanManager(AgentManager):
    """
    Manager for all Japanese Agents
    """

    def __init__(self):
        super().__init__()

        self.initiate_bases()
        self.initiate_agents()

        self.calculate_utilization_rates()

    def __str__(self):
        return "Japan Agent Manager"

    def initiate_bases(self) -> None:
        pass

    def initiate_agents(self) -> None:
        pass
