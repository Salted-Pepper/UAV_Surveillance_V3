from agent import Agent
import constants
import model_info

import random
import copy
from points import Point
from base import Harbour

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
    def __init__(self, base, obstacles: list, color: str):
        super().__init__(base, obstacles, color)

        global ship_id
        self.ship_id = ship_id
        ship_id += 1

        self.ship_type = None
        self.RCS = None

        # ---- Ship Specific Status -----
        self.entry_point = None
        self.enter_world_time = None
        self.boarded = False
        self.CTL = False
        self.damage_penalty = 0

        self.pheromone_spread = -100

    def enter_world(self) -> None:
        self.enter_world_time = constants.world.world_time
        self.generate_ship_entry_point()

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

    def enter_dock(self):
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
                :return:
                """
        print(f"{self.ship_type} {self.ship_id} sunk at ({self.location.x}, {self.location.y}).")
        for uav in self.trailing_agents:
            uav.perceive_ship_sunk()

        self.destroyed = True
        self.route = None
        constants.world.ship_destroyed(self)
        self.remove_from_plot()


class Merchant(Ship):
    def __init__(self, model: str, base: Harbour, obstacles: list):
        super().__init__(base, obstacles, constants.MERCHANT_COLOR)
        self.max_health = constants.MERCHANT_HEALTH

        self.base = base

        self.model = model

        self.cargo_load = None
        self.RCS = None

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

    def reached_end_of_route(self) -> None:
        self.route = None
        self.enter_dock()
        for agent in self.trailing_agents:
            agent.stop_trailing("Merchant Target has reached a Port")

    def return_to_base(self) -> None:
        """
        Merchants don't have a fixed base.
        Start a retreat process, generate a route back out of the area of interest
        :return:
        """
        print(f"{self.ship_type} {self.ship_id} is retreating with {self.health_points=}")
        if self.routing_to_base:
            return
        else:
            self.routing_to_base = True
            self.generate_route(destination=self.entry_point)

    def complete_maintenance(self):
        self.health_points = self.max_health


def generate_random_merchant(world) -> Merchant:
    model = random.choices(["Cargo", "Container", "Bulk"],
                           [constants.CARGO_DAILY_ARRIVAL_MEAN,
                            constants.BULK_DAILY_ARRIVAL_MEAN,
                            constants.CONTAINER_DAILY_ARRIVAL_MEAN])[0]
    base = random.choices(constants.world.docks, weights=[0.4, 0.3, 0.25, 0.05], k=1)[0]
    return Merchant(model=model, base=base, obstacles=world.polygons)


class Escort(Ship):
    def __init__(self, model: str, base: Harbour, obstacles: list, color: str):
        super().__init__(base, obstacles, color)
        self.health = constants.ESCORT_HEALTH

        self.model = model
        self.length = None
        self.displacement = None
        self.armed = None
        self.max_speed = None
        self.contains_helicopter = None
        self.endurance = None

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

    def start_guarding(self, unit):
        unit.being_guarded = True
        self.guarding_target = unit

    def select_guarding_target(self):
        """
                Task the escort to find a target to guard. Returns True if a successful target is established,
                False otherwise.
                :return:
                """
        merchants = [vessel for vessel in constants.world.current_vessels
                     if vessel.ship_type == "Merchant" and not vessel.being_guarded]

        # TODO: refine how a target is selected - for now just closest unguarded merchant
        if len(merchants) == 0:
            return False

        escort_location = self.location
        merchant = min(merchants, key=lambda m: escort_location.distance_to_point(m.location))
        self.start_guarding(merchant)
        return True

    def reached_end_of_route(self) -> None:
        self.route = None

        if self.routing_to_base:
            self.enter_dock()
            for agent in self.trailing_agents:
                agent.stop_trailing("Escort Target has reached a Port")
        elif self.routing_to_patrol:
            pass
        else:
            raise ValueError("Escort reached end of unexpected route.")

    def return_to_base(self) -> None:
        self.generate_route(destination=self.base)
        self.routing_to_base = True


class USEscort(Escort):
    def __init__(self, model: str, base: Harbour, obstacles: list):
        super().__init__(model, base, obstacles, constants.US_ESCORT_COLOR)

    def make_move(self):
        """
        Make next move based on behaviour and rules.
        :return:
        """
        pass


class JapanEscort(Escort):
    def __init__(self, model: str, base: Harbour, obstacles: list):
        super().__init__(model, base, obstacles, constants.JAPAN_ESCORT_COLOR)

    def make_move(self):
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
        super().__init__(model, base, obstacles, constants.TAIWAN_ESCORT_COLOR)

    def make_move(self):
        """
        Make next move based on behaviour and rules.
        :return:
        """
        if constants.taiwan_engagement == "attack_all":
            pass
        elif constants.taiwan_engagement == "engaged_only":
            pass
        else:
            raise NotImplementedError(f"Unknown engagement tactic {constants.taiwan_engagement}")
