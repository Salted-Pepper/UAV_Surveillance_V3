from ships import TaiwanEscort, Merchant
from base import Base, Harbour, Airbase
from drones import Drone

from points import Point

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
            self.utilization_rates['model'] = (
                    (agent_of_model.endurance - (2 * min_time_to_travel + min_time_to_trail)) /
                    (agent_of_model.endurance + agent_of_model.maintenance_time))

    def manage_agents(self):
        for base in self.bases:
            base.serve_agents()

        # Check if agent needs to return for resupply
        active_agents = [agent for agent in self.agents if not agent.stationed]
        for agent in active_agents:
            if isinstance(agent, Merchant):
                # Merchants don't have a limit on endurance, so we skip those
                continue

            distances_to_bases = []
            for base in self.bases:
                distances_to_bases.append([agent.location.distance_to_point(base.location), base])

            distance_to_resupply, base = min(distances_to_bases, key=lambda x: x[0])
            if agent.remaining_endurance < (distance_to_resupply / agent.speed) * constants.SAFETY_ENDURANCE:
                agent.go_resupply(base)

        # Check if utilization is satisfied - if not, send out new agents if feasible
        for model in set([agent.model for agent in self.agents]):
            agents_of_model = [agent for agent in self.agents if agent.model == model]
            active_agents = [agent for agent in agents_of_model if not agent.docked]
            current_utilization = len(active_agents) / len(agents_of_model)
            available_inactive_agents = [agent for agent in agents_of_model
                                         if agent.remaining_service_time == 0 and agent.docked]

            # TODO: OPTIONAL See if we can launch more than one per timestep?
            #  - maybe depending on length of timestep?
            if current_utilization < 1:
                np.random.choice(available_inactive_agents)

    def select_random_base(self):
        return np.random.choice(self.bases)


class MerchantManager(Manager):
    """
    Manager for all 'neutral' Merchants
    """

    def __init__(self):
        super().__init__()

        self.initiate_bases()

    def initiate_bases(self):
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
        return np.random.choice(self.bases, p=[base.probability for base in self.bases])

    def generate_new_merchant(self):
        model = np.random.choice(a=["Cargo", "Container", "Bulk"],
                                 p=[constants.CARGO_DAILY_ARRIVAL_MEAN,
                                    constants.BULK_DAILY_ARRIVAL_MEAN,
                                    constants.CONTAINER_DAILY_ARRIVAL_MEAN])
        base = self.select_random_base()
        self.agents.append(Merchant(model, base))



class USManager(Manager):
    """
    Manager for all US Agents
    """

    def __init__(self):
        super().__init__()

        self.initiate_bases()
        self.initiate_agents()

    def initiate_bases(self):
        pass

    def initiate_agents(self):
        pass


class TaiwanManager(Manager):
    """
    Manager for all Taiwanese Agents
    """

    def __init__(self):
        super().__init__()

        self.initiate_bases()
        self.initiate_agents()

    def initiate_bases(self):
        pass

    def initiate_agents(self):
        self.agents = [TaiwanEscort(name="Test Escort",
                                    model="Zhaotou",
                                    base=self.select_random_base(),
                                    obstacles=constants.world.polygons)]


class JapanManager(Manager):
    """
    Manager for all Japanese Agents
    """

    def __init__(self):
        super().__init__()

        self.initiate_bases()
        self.initiate_agents()

    def initiate_bases(self):
        pass

    def initiate_agents(self):
        pass
