from agent import Agent
from points import Point
from base import Base

from general_maths import calculate_distance
import constants
import model_info
from ships import Ship

import math
import copy
import time
import numpy as np

import os
import logging
import datetime

date = datetime.date.today()
logging.basicConfig(level=logging.DEBUG, filename=os.path.join(os.getcwd(), 'logs/navy_log_' + str(date) + '.log'),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt="%H:%M:%S")
logger = logging.getLogger("UAV")
logger.setLevel(logging.DEBUG)

uav_id = 0


class DroneType:
    def __init__(self, model: str, amount: int):
        self.model = model
        self.total = amount
        self.drones = []

        self.airborne = 0
        self.destroyed = 0
        self.grounded = amount
        self.under_maintenance = 0

        self.utilization_rate = None

    def drone_landed(self):
        self.airborne -= 1
        self.grounded += 1
        self.under_maintenance += 1

    def calculate_utilization_rate(self) -> None:
        # TODO: Implement function for utilization rate
        self.utilization_rate = 0.15

    def reached_utilization_rate(self) -> bool:
        """
        Checks if we should launch more drones to satisfy the utilization rate
        :return:
        """
        if (self.airborne + 1) / (self.total - self.destroyed) > self.utilization_rate:
            return True
        else:
            return False


class Drone(Agent):
    def __init__(self, model: str, base: Base, obstacles: list, drone_type: DroneType):
        super().__init__(2, base, obstacles, constants.UAV_COLOR)
        global uav_id
        self.uav_id = uav_id
        self.drone_type = drone_type
        uav_id += 1

        self.RCS = 0
        self.vulnerability = None
        self.ability_to_target = None
        self.range = None

        self.pheromone_spread = 100

        self.model = model
        self.initiate_model()

    def __str__(self):
        return f"U {self.uav_id}"

    def calculate_maintenance_time(self) -> None:
        """
        Calculates maintenance times for the type of UAV
        :return:
        """
        self.maintenance_time = 3.4 + 0.68 * self.endurance

    def move(self, distance_to_travel=None):
        """
        Make the move for the current time step.
        Depends on if they are travelling to a destination (base/start point), patrolling, or trailing.
        :return:
        """
        if distance_to_travel is None:
            distance_to_travel = self.speed * constants.world.time_delta

        self.last_location = copy.deepcopy(self.location)
        t_0 = time.perf_counter()

        self.time_spent_from_base += constants.world.time_delta

        # Case 1: Check if the UAV has to return to base if not already
        if not self.routing_to_base:
            if not self.can_continue():
                logger.debug(f"Checking after can_continue function for {self.uav_id}")
                if constants.DEBUG_MODE:
                    self.debug()
                self.return_to_base()
                self.time_spent_from_base += constants.world.time_delta
                t_1 = time.perf_counter()
                constants.time_spent_checking_uav_return += (t_1 - t_0)
                return
        t_1 = time.perf_counter()
        constants.time_spent_checking_uav_return += (t_1 - t_0)

        # Case 2: Requested support
        if self.awaiting_support:
            if self.support_object.is_near(self.located_agent.location):
                self.stop_trailing(reason="Support Arrived")
                self.awaiting_support = False
                self.support_object = None
                return

        # Case 3: Following a route
        if self.routing_to_patrol or self.routing_to_base or self.trailing:
            t_0 = time.perf_counter()

            # Case 3.1: Trailing a ship - update route to new ship location before chasing
            if self.trailing:
                self.update_trail_route()
                t_1 = time.perf_counter()
                constants.time_spent_updating_trail_route += (t_1 - t_0)

            # Case 3.X: Moving through the route
            t_0 = time.perf_counter()
            self.move_through_route(distance_to_travel)
            t_1 = time.perf_counter()
            constants.time_spent_following_route += (t_1 - t_0)

            # Case 3.1 continued:
            if self.trailing:
                if self.is_near(self.located_agent.location):
                    self.call_action_on_agent()

        # Case 4: Patrolling an area
        elif self.patrolling:
            self.make_next_patrol_move()

        # Check if drone is in legal location
        if constants.DEBUG_MODE:
            self.debug()

    def activate(self, to_patrol=True, target=None):
        """
        Launch a drone to either a target or to patrol an area
        :param to_patrol:
        :param target:
        :return:
        """
        constants.world.current_airborne_drones.append(self)
        self.stationed = False
        self.drone_type.airborne += 1

        if to_patrol:
            start_location = self.generate_patrol_location()
            start_location.name = "Start Location"
            logger.debug(f"Launching UAV {self.uav_id} to {start_location}")
            self.generate_route(start_location)
            self.routing_to_patrol = True
            self.move()
        elif target is not None:
            start_location = target.location
            logger.debug(f"Launching UAV {self.uav_id} to {target}")
            self.generate_route(start_location)
            self.trailing = True
            self.move()

    def return_to_base(self):
        logger.debug(f"UAV {self.uav_id} is forced to return to base.")
        self.routing_to_patrol = False

        if self.trailing:
            self.stop_trailing("Running Low On Endurance")

        self.generate_route(self.base.location)
        self.routing_to_base = True

    def land(self):
        logger.debug(f"UAV {self.uav_id} landed at {self.location} - starting maintenance")

        self.stationed = True
        self.update_plot()

        constants.world.current_airborne_drones.remove(self)
        self.drone_type.drone_landed()

        self.past_points = []
        self.time_spent_from_base = 0
        self.start_maintenance()

    def initiate_model(self) -> None:
        logger.debug(f"Initiating drone of type {self.model}.")
        for blueprint in model_info.UAV_MODELS:
            if blueprint['name'] == self.model:
                self.speed = blueprint['speed']
                self.vulnerability = blueprint['vulnerability']
                self.ability_to_target = blueprint['ability_to_target']
                self.max_ammunition = blueprint['max_ammunition']
                self.ammunition = self.max_ammunition
                self.radius = blueprint['radius']
                self.endurance = blueprint['endurance']
                self.range = blueprint['range']

                self.calculate_maintenance_time()
                return

    def go_resupply(self, base):
        """
        Function to be defined on agent level to ensure actions are ended correctly
        :param: base - Forced by Parent, but not used here, as UAVs can not return to other bases
        :return:
        """
        logger.debug(f"UAV {self.uav_id} is forced to return to base.")
        self.routing_to_patrol = False

        if self.trailing:
            self.stop_trailing("Running Low On Endurance")

        self.generate_route(self.base.location)
        self.routing_to_base = True

    def reached_end_of_route(self) -> None:
        """
        Set of instructions to follow once the end of agent route is reached.
        - If reaching patrol location: start patrol
        - If reaching a base: Land
        - If reaching trailed object: take action
        :return:
        """
        if constants.DEBUG_MODE:
            if self.route_plot is not None:
                for lines in self.route_plot:
                    line = lines.pop(0)
                    line.remove()
                self.route_plot = None

        self.route = None

        if self.routing_to_patrol:
            self.routing_to_patrol = False
            self.patrolling = True
            self.move(self.distance_to_travel)
        elif self.routing_to_base:
            self.routing_to_base = False
            self.land()
        elif self.trailing:
            pass
        else:
            NotImplementedError("Exception - reached end of route, but not trailing, patrolling, or landing.")

    @staticmethod
    def roll_detection_check(uav_location, agent: Agent, distance: float = None) -> float:
        if distance is None:
            distance = calculate_distance(a=uav_location, b=agent.location)

        # Get weather conditions in area
        closest_receptor = constants.world.receptor_grid.get_closest_receptor(agent.location)
        sea_state = closest_receptor.sea_state
        sea_state_to_parameter = {0: 0.89,
                                  1: 0.89,
                                  2: 0.77,
                                  3: 0.68,
                                  4: 0.62,
                                  5: 0.53,
                                  6: 0.47}

        if sea_state < 7:
            weather = sea_state_to_parameter[sea_state]
        else:
            weather = 0.40

        height = 10  # Assumed to be 10km
        print(f"{agent=}, {height=}, {agent.RCS=}, {weather=}")
        top_frac_exp = constants.K_CONSTANT * height * agent.RCS * weather
        if distance < 1:
            distance = 1
        delta = 1 - math.exp(-top_frac_exp / (distance ** 3))
        return delta

    def observe_area(self) -> None:
        t_0 = time.perf_counter()
        active_hostile_ships = [agent
                                for manager in constants.world.managers
                                for agent in manager.agents
                                if agent.team != self.team]
        for ship in active_hostile_ships:
            detection_probabilities = []

            radius_travelled = self.radius + self.speed * constants.world.time_delta

            if calculate_distance(a=self.location, b=ship.location) > radius_travelled:
                continue

            if len(ship.trailing_agents) > 0:
                continue

            for lamb in np.append(np.arange(0, 1, step=1 / constants.world.splits_per_step), 1):
                uav_location = Point(self.location.x * lamb + self.last_location.x * (1 - lamb),
                                     self.location.y * lamb + self.last_location.y * (1 - lamb))
                distance = calculate_distance(a=uav_location, b=ship.location)
                if distance <= self.radius:
                    detection_probabilities.append(self.roll_detection_check(uav_location, ship, distance))
            probability = 1 - np.prod(
                [(1 - p) ** (1 / constants.world.splits_per_step) for p in detection_probabilities])
            if np.random.rand() <= probability:
                # logger.debug(f"UAV {self.uav_id} detected {ship.ship_id} - w/ prob {probability}. "
                #              f"- {self.routing_to_base=}")
                if not self.routing_to_base:
                    self.start_trailing(ship)
                t_1 = time.perf_counter()
                constants.time_spent_observing_area += (t_1 - t_0)
                return
            else:
                # logger.debug(f"UAV {self.uav_id} failed to detect ship {ship.ship_id} - detect prob {probability}.")
                pass

        t_1 = time.perf_counter()
        constants.time_spent_observing_area += (t_1 - t_0)

    def engage_agent(self):
        """
        Attacks targeted vessel.
        :return:
        """
        logger.debug(f"UAV {self.uav_id} attacking {self.located_agent.ship_id}")
        if self.ammunition == 0:
            raise ValueError(f"UAV {self.uav_id} attempting to attack without available ammunition")

        damage = np.random.randint(0, 101)
        self.located_agent.receive_damage(damage)

    def perceive_ship_sunk(self):
        self.stop_trailing(f"UAV Reports Target {self.located_agent} is Sunk")

    def call_in_support(self):
        options = []
        for uav in constants.world.current_airborne_drones:
            if uav.ammunition > 0 and uav.reach_and_return(self.located_agent.location) and not uav.routing_to_base:
                options.append([uav, self.location.distance_to_point(uav.location)])

        if len(options) == 0:
            logger.debug(f"No supporting UAV available, gave up on the chase")
            self.stop_trailing("No Action Capacity")
            return
        else:
            selected_support = min(options, key=lambda x: x[1])[0]

            if selected_support.routing_to_base:
                raise PermissionError(f"Calling Occupied UAV {self.uav_id}")

        self.awaiting_support = True
        selected_support.start_trailing(self.located_agent)
        self.support_object = selected_support
        logger.debug(f"UAV {self.uav_id} calling in UAV {selected_support.uav_id} "
                     f"to attack ship {self.located_agent.ship_id}")

    def sample_random_patrol_start(self) -> Point:
        # TODO: make dependent on endurance and range of the UAV (In a more sophisticated way)
        x = np.random.uniform(constants.PATROL_MIN_LAT,
                              constants.PATROL_MAX_LAT)
        y = np.random.uniform(constants.PATROL_MIN_LONG,
                              min(constants.PATROL_MAX_LONG, constants.PATROL_MIN_LONG + (self.range / 2)))
        return Point(x, y)

    def generate_patrol_location(self) -> Point:
        points = [self.sample_random_patrol_start() for _ in range(constants.PATROL_LOCATIONS)]
        concentration_of_pheromones = []
        for point in points:
            cop, _ = constants.world.receptor_grid.calculate_CoP(point, self.radius)
            concentration_of_pheromones.append(cop)
        # currently selecting minimal location - could do weight based sampling instead
        min_index = concentration_of_pheromones.index(min(concentration_of_pheromones))
        return points[min_index]

    def complete_maintenance(self):
        self.under_maintenance = False
        self.ammunition = self.max_ammunition
        self.health_points = constants.UAV_HEALTH
        self.time_spent_from_base = 0
