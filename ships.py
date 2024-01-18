from agent import Agent
import constants
import model_info

import numpy as np
import random
import copy

from points import Point
from base import Harbour
from general_maths import calculate_distance

import os
import logging
import datetime

date = datetime.date.today()
logging.basicConfig(level=logging.DEBUG, filename=os.path.join(os.getcwd(), 'logs/navy_log_' + str(date) + '.log'),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt="%H:%M:%S")
logger = logging.getLogger("SHIPS")
logger.setLevel(logging.WARNING)

ship_id = 0


class Ship(Agent):
    def __init__(self, team: int, base: Harbour, obstacles: list, color: str):
        super().__init__(team, base, obstacles, color)

        global ship_id
        self.ship_id = ship_id
        ship_id += 1

        self.ship_type = None

        # ---- Ship Specific Status -----
        self.entry_point = None
        self.enter_world_time = None
        self.boarded = False
        self.CTL = False
        self.damage_penalty = 0

        self.pheromone_spread = 100

    def __str__(self):
        return f"S {self.ship_id}"

    def enter_world(self) -> None:
        self.stationed = False
        self.enter_world_time = constants.world.world_time
        self.generate_ship_entry_point()
        self.generate_route(self.base.location)

    def generate_ship_entry_point(self) -> None:
        """
        Generates random y coordinate at which ship enters on the East Coast
        :return:
        """
        longitude = random.uniform(constants.MIN_LONG, constants.MAX_LONG)
        latitude = constants.MAX_LAT

        self.entry_point = Point(latitude, longitude)
        self.location = copy.deepcopy(self.entry_point)
        logger.debug(f"{self.ship_type} {self.ship_id} enters at {self.entry_point}")
        self.routing_to_base = True

    def enter_dock(self):
        self.remove_trailing_agents("Merchant reached safe dock")
        self.remove_guarding_agents()
        logger.debug(f"{self} reached dock")
        self.routing_to_base = False
        self.stationed = True
        self.start_maintenance()

    def receive_damage(self, damage: int) -> None:
        """
        Receive damage from drone attack and adjust behaviour according to result
        :param damage:
        :return:
        """

        damage = damage + 10 * self.damage_penalty
        self.health_points -= damage
        logger.debug(f"{self.ship_type} {self.ship_id} received {damage} damage. New health: {self.health_points}")

        # Set Damage Effects
        if self.health_points >= 81:
            return
        elif self.health_points >= 71:
            pass
        elif self.health_points >= 47:
            self.damage_penalty = 1
        elif self.health_points >= 21:
            self.damage_penalty = 2
        # TODO : Address 9-16 range (CTL but not retreating?)
        elif self.health_points >= 9:
            self.CTL = True
            self.damage_penalty = 2
        else:
            self.sinking()
            return

        # retreat unless health > 81 or sunk
        self.return_to_base()

    def sinking(self):
        """
        Ship sank, remove from world, update statistics.
        Ship automatically gets moved to "destroyed" section in agent Manager
        :return:
        """
        print(f"{self.ship_type} {self.ship_id} sunk at ({self.location.x}, {self.location.y}).")
        for uav in self.trailing_agents:
            uav.perceive_ship_sunk()

        self.destroyed = True
        self.route = None
        self.remove_from_plot()


class Merchant(Ship):
    def __init__(self, model: str, base: Harbour, obstacles: list):
        super().__init__(1, base, obstacles, constants.MERCHANT_COLOR)
        self.health_points = constants.MERCHANT_HEALTH
        self.max_health = constants.MERCHANT_HEALTH

        self.base = base

        self.model = model

        self.maintenance_time = constants.MERCHANT_MAINTENANCE_TIME
        self.leaving_world = False
        self.cargo_load = None
        self.RCS = None

        self.radius = 0

        self.initiate_parameters()

    def initiate_parameters(self) -> None:
        if self.model == "Cargo":
            self.speed = constants.CARGO_AVERAGE_SPEED
            self.cargo_load = constants.CARGO_AVERAGE_LOAD
            self.RCS = constants.CARGO_RCS
        elif self.model == "Bulk":
            self.speed = constants.BULK_AVERAGE_SPEED
            self.cargo_load = constants.BULK_AVERAGE_LOAD
            self.RCS = constants.BULK_RCS
        elif self.model == "Container":
            self.speed = constants.CONTAINER_AVERAGE_SPEED
            self.cargo_load = constants.CONTAINER_AVERAGE_LOAD
            self.RCS = constants.CONTAINER_RCS
        else:
            raise NotImplementedError(self.model)

    def move(self, distance_to_travel=None):
        self.move_through_route(distance_to_travel)

    def activate(self):
        self.stationed = False
        self.leaving_world = True
        self.generate_route(self.entry_point)

    def complete_maintenance(self):
        logger.debug(f"{self} finished maintenance.")
        self.health_points = self.max_health
        self.ammunition = self.max_ammunition
        self.activate()

    def receive_damage(self, damage: int) -> None:
        """
        Receive damage from drone attack and adjust behaviour according to result
        :param damage:
        :return:
        """

        damage = damage + 10 * self.damage_penalty
        self.health_points -= damage
        logger.debug(f"{self.ship_type} {self.ship_id} received {damage} damage. New health: {self.health_points}")

        # Set Damage Effects
        if self.health_points >= 81:
            return
        elif self.health_points >= 71:
            pass
        elif self.health_points >= 47:
            self.damage_penalty = 1
        elif self.health_points >= 21:
            self.damage_penalty = 2
        # TODO : Address 9-16 range (CTL but not retreating?)
        elif self.health_points >= 9:
            self.CTL = True
            self.damage_penalty = 2
        else:
            self.sinking()
            return

        # retreat unless health > 81 or sunk
        self.start_retreat()

    def start_retreat(self) -> None:
        """
        Start retreat process, generate a route back out of the area of interest
        :return:
        """
        print(f"{self} is retreating with {self.health_points=}")
        if self.leaving_world:
            return
        else:
            self.leaving_world = True
            self.generate_route(destination=self.entry_point)

    def reached_end_of_route(self) -> None:
        """
        Set of instructions to follow once the end of agent route is reached.
        Not provided on Agent level
        :return:
        """
        self.distance_to_travel = 0
        self.route = None

        if self.leaving_world:
            self.stationed = True
            self.remove_trailing_agents("Merchant left world")
        elif self.routing_to_base:
            self.enter_dock()
        self.remove_from_plot()


def generate_random_merchant() -> Merchant:
    model = random.choices(["Cargo", "Container", "Bulk"],
                           [constants.CARGO_DAILY_ARRIVAL_MEAN,
                            constants.BULK_DAILY_ARRIVAL_MEAN,
                            constants.CONTAINER_DAILY_ARRIVAL_MEAN])[0]
    base = random.choices(constants.world.docks, weights=[0.4, 0.3, 0.25, 0.05], k=1)[0]
    return Merchant(model=model, base=base, obstacles=constants.world.landmasses)


class Escort(Ship):
    def __init__(self, team: int, model: str, base: Harbour, obstacles: list, color: str):
        super().__init__(team, base, obstacles, color)
        self.health = constants.ESCORT_HEALTH

        self.model = model
        self.RCS = 3  # TODO: Implement proper RCS for escorts
        self.radius = 10  # TODO: Implement proper search radius for escorts
        self.length = None
        self.displacement = None
        self.armed = None
        self.max_speed = None
        self.contains_helicopter = None
        # TODO: Implement Individual maint time for Escorts
        self.maintenance_time = constants.ESCORT_MAINTENANCE_TIME

        self.speed = constants.CRUISING_SPEED

        self.guarding_target = None
        self.behaviour = None

        self.initiate_model()

    def initiate_model(self):
        for blueprint in model_info.ESCORT_MODELS:
            if blueprint['name'] == self.model:
                self.length = blueprint['length']
                self.displacement = blueprint['displacement']
                self.armed = blueprint['armed']
                self.max_speed = blueprint['max_speed']
                self.contains_helicopter = blueprint['helicopter']
                self.endurance = blueprint['endurance']

    def make_move(self):
        raise NotImplementedError(f"Behaviour {self.behaviour} not implemented for baseclass ESCORT.")

    def start_guarding(self, agent):
        agent.guarding_agents.append(self)
        self.guarding_target = agent
        self.generate_route(self.guarding_target.location)

    def stop_guarding(self):
        self.guarding_target = None

    def activate(self):

        self.stationed = False

        # TODO: determine how to set behaviour mode - for now sample random one
        behaviours = constants.taiwan_escort_behaviour
        self.behaviour = random.choices(list(behaviours.keys()),
                                        [behaviours[behaviour]
                                         for behaviour in behaviours.keys()]
                                        )[0]

        if self.behaviour == "patrol":
            self.generate_route(self.generate_patrol_location())
            self.routing_to_patrol = True
        elif self.behaviour == "guard":
            found_target = self.select_guarding_target()
            if not found_target:
                self.patrolling = True
        # TODO: Make activation rules based on hunting behaviour

    def reached_end_of_route(self) -> None:
        self.distance_to_travel = 0
        self.route = None

        if self.routing_to_base:
            self.enter_dock()
            for agent in self.trailing_agents:
                agent.stop_trailing("Escort Target has reached a Port")
        elif self.routing_to_patrol:
            self.patrolling = True
            self.make_next_patrol_move()
        elif self.guarding_target is not None:
            self.distance_to_travel = 0
            self.observe_area()
        else:
            raise ValueError("Escort reached end of unexpected route.")

    def generate_patrol_location(self):
        logger.warning(f"Using default ESCORT class patrol generation - needs to be refined for {self}")
        x = np.random.choice(np.arange(130, 150, 0.1))
        y = np.random.choice(np.arange(8, 28, 0.1))
        return Point(x, y, name=f"Patrol Location {self.ship_id}")

    def select_guarding_target(self):
        """
        Task the escort to find a target to guard. Returns True if a successful target is established,
        False otherwise.
        :return:
        """
        merchants = [vessel for vessel in constants.world.current_vessels
                     if vessel.ship_type == "Merchant" and not len(vessel.guarding_agents) == 0]

        # TODO: refine how a target is selected - for now just closest unguarded merchant
        if len(merchants) == 0:
            return False

        escort_location = self.location
        merchant = min(merchants, key=lambda m: escort_location.distance_to_point(m.location))
        self.start_guarding(merchant)
        return True

    def observe_area(self) -> None:
        active_hostile_agents = [agent
                                 for manager in constants.world.managers
                                 for agent in manager.agents
                                 if agent.team != self.team]
        for agent in active_hostile_agents:
            detection_probabilities = []

            radius_travelled = self.radius + self.speed * constants.world.time_delta

            if calculate_distance(a=self.location, b=agent.location) > radius_travelled:
                continue

            if len(agent.trailing_agents) > 0:
                continue

            for lamb in np.append(np.arange(0, 1, step=1 / constants.world.splits_per_step), 1):
                own_location = Point(self.location.x * lamb + self.last_location.x * (1 - lamb),
                                     self.location.y * lamb + self.last_location.y * (1 - lamb))
                distance = calculate_distance(a=own_location, b=agent.location)
                if distance <= self.radius:
                    detection_probabilities.append(self.roll_detection_check(own_location, agent, distance))
            probability = 1 - np.prod(
                [(1 - p) ** (1 / constants.world.splits_per_step) for p in detection_probabilities])
            if np.random.rand() <= probability:
                if not self.routing_to_base:
                    self.start_trailing(agent)
                return
            else:
                pass

    def return_to_base(self) -> None:
        self.guarding_target = False
        self.routing_to_patrol = False
        self.generate_route(destination=self.base)
        self.routing_to_base = True

    def roll_detection_check(self, own_location: Point, agent: Point, distance: float):
        raise NotImplementedError("Detection check not implemented on ESCORT level.")


class USEscort(Escort):
    def __init__(self, model: str, base: Harbour, obstacles: list):
        super().__init__(1, model, base, obstacles, constants.US_ESCORT_COLOR)

    def make_move(self):
        """
        Make next move based on behaviour and rules.
        :return:
        """
        self.distance_to_travel = self.speed * constants.world.time_delta

        if self.routing_to_base or self.routing_to_patrol:
            self.move_through_route()

        if self.distance_to_travel > 0:
            self.make_next_patrol_move()

    def observe_area(self):
        pass


class JapanEscort(Escort):
    def __init__(self, model: str, base: Harbour, obstacles: list):
        super().__init__(1, model, base, obstacles, constants.JAPAN_ESCORT_COLOR)

    def engage_agent(self):
        """
        Make next move based on behaviour and rules.
        :return:
        """
        rule = constants.japan_engagement
        if rule == "never attack":
            pass
        elif rule == "attack_territorial":
            pass
        elif rule == "attack_contiguous_zone":
            pass
        elif rule == "attack_inner_ADIZ":
            pass
        elif rule == "attack_outer_ADIZ":
            pass
        elif rule == "attack_all":
            pass
        else:
            raise NotImplementedError(f"Unknown engagement tactic {constants.japan_engagement}")


class TaiwanEscort(Escort):
    def __init__(self, model: str, base: Harbour, obstacles: list):
        super().__init__(1, model, base, obstacles, constants.TAIWAN_ESCORT_COLOR)

        self.pheromone_type = "Alpha"

    def make_move(self):
        """
        Make next move based on behaviour and rules.
        :return:
        """
        self.distance_to_travel = self.speed * constants.world.time_delta
        self.move()
        self.update_plot()

    def move(self, distance_to_travel=None):
        if distance_to_travel is not None:
            self.distance_to_travel = distance_to_travel

        print(f"Moving {self}: {self.distance_to_travel}, {self.trailing}, {self.behaviour}, {self.routing_to_patrol}")
        while self.distance_to_travel > 0:
            if self.trailing:
                if self.is_near(self.located_agent.location):
                    self.call_action_on_agent()
                    self.distance_to_travel = 0

            if self.behaviour == "patrol":
                if self.routing_to_patrol:
                    self.move_through_route()
                else:
                    self.make_next_patrol_move()

            elif self.behaviour == "guard":
                if self.guarding_target is not None:
                    self.generate_route(self.guarding_target.location)
                    self.move_through_route()
                else:
                    able_to_select_target = self.select_guarding_target()
                    if not able_to_select_target:
                        self.make_next_patrol_move()

            else:
                raise NotImplementedError(f"Behaviour {self.behaviour} not implemented!")

    def roll_detection_check(self, own_location: Point, agent_location: Point, distance: float) -> float:
        # TODO: Implement proper escort detection check
        return 0.9
