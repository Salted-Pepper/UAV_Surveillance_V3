import constants
from points import Point
from routes import create_route, Route
from general_maths import calculate_distance
import copy

import numpy as np
import math
import matplotlib.patches

import os
import logging
import datetime

date = datetime.date.today()
logging.basicConfig(level=logging.DEBUG, filename=os.path.join(os.getcwd(), 'logs/log_' + str(date) + '.log'),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt="%H:%M")
logger = logging.getLogger("AGENT")
logger.setLevel(logging.DEBUG)


class Agent:
    def __init__(self, team: int, base, obstacles: list, color: str):
        """
        Agents - Either UAVs, Submarines, or a Vessel
        :param base: Where the agent returns when retreating and/or resupplying
        :param obstacles: Areas the agent can not pass through
        :param color: color the agent is plotted as
        """
        self.team = team
        self.model = None

        # ----- GEO DATA ON AGENT ------
        self.base = base
        self.obstacles = obstacles
        self.manager = None  # Object that is responsible to manage actions of the agent

        # ----- PROPERTIES OF AGENT ------
        self.location = base.location

        self.RCS = None
        self.speed = None
        self.radius = None
        self.max_health = None
        self.health_points = None
        self.able_to_attack = False
        self.max_ammunition = None
        self.ammunition = None
        self.endurance = None

        self.pheromone_type = None

        # ----- STATE OF AGENT -----
        self.distance_to_travel = 0

        self.time_spent_from_base = 0
        self.routing_to_base = False
        self.stationed = True
        self.destroyed = False
        self.left_world = False

        self.routing_to_patrol = False
        self.patrolling = False
        self.pheromone_spread = None
        self.direction = "north"  # Direction facing when patrolling to make subsequent moves

        self.trailing = False
        self.located_agent = None
        self.detected = False
        self.trailing_agents = []
        self.guarding_agents = []
        self.awaiting_support = False
        self.support_object = None

        self.under_maintenance = False
        self.maintenance_time = None
        self.remaining_maintenance_time = 0

        # ----- ROUTE OF AGENT -----
        self.route = None
        self.last_location = None
        self.past_points = []
        self.next_point = None
        self.remaining_points = None

        # ----- PLOTTING OF AGENT -----
        self.radius_patch = None
        self.route_plot = None
        self.color = color
        self.marker = None
        self.text = None

    def generate_route(self, destination: Point = None) -> None:
        """
        Creates a route from current location to a certain point, while avoiding the default list of obstacles
        provided for the agent
        :param destination: Reachable location for the agent
        :return:
        """
        self.route = create_route(point_a=self.location, point_b=destination,
                                  polygons_to_avoid=copy.deepcopy(self.obstacles))
        self.past_points.append(self.route.points[0])
        self.last_location = self.location
        self.next_point = self.route.points[1]
        self.remaining_points = self.route.points[2:]

    def activate(self):
        """
        Function to be overwritten on lower level -
        Activation is what the agent will do once it is entered into the world.
        :return:
        """
        raise NotImplementedError("Function ACTIVATE not defined on AGENT level.")

    def update_trail_route(self) -> None:
        """
        Update the agents route to route it to the located agent that it is trailing.
        :return:
        """
        if self.located_agent is not None:
            if self.located_agent.stationed or self.located_agent.left_world:
                logger.debug(f"Agent {self} is forced to stop chasing {self.located_agent} "
                             f"- reached destination or left world.")
                self.stop_trailing("Target Reached Destination")
                return

            for polygon in self.obstacles:
                if polygon.check_if_contains_point(self.located_agent.location):
                    logger.debug(
                        f"Agent {self} is forced to stop chasing {self.located_agent} - in safe zone.")
                    self.stop_trailing("Target Entered Safe Zone")
                    return

        self.generate_route(destination=self.located_agent.location)
        if constants.DEBUG_MODE:
            self.debug()

    def start_trailing(self, agent) -> None:
        """
        Make this agent start trailing the provided agent.
        :param agent: Agent to start following
        :return:
        """
        if self.routing_to_patrol:
            self.routing_to_patrol = False
        elif self.routing_to_base:
            logger.warning(f"Tried calling Agent {self} for trailing while routing to base - Continuing going back")
            return

        self.patrolling = False
        self.trailing = True
        agent.trailing_agents.append(self)
        self.located_agent = agent
        self.update_trail_route()

    def stop_trailing(self, reason: str) -> None:
        """
        Makes the agent stop trailing any agent it is trailing.
        :param reason: String describing why the trailing was aborted
        :return:
        """
        if self.trailing:
            self.trailing = False
            logger.debug(f"{self} stopped trailing {self.located_agent} - {reason}")

            self.located_agent.trailing_agents.remove(self)
            self.located_agent = None
            self.awaiting_support = False
            self.support_object = None

            self.stopped_trailing()
        else:
            logger.error(f"Agent {self} was not trailing - ordered to stop trailing {self.located_agent}")

    def stopped_trailing(self, ):
        """
        Course of action for agent to take after stopping trailing
        """
        self.move(self.distance_to_travel)

    def remove_trailing_agents(self, reason: str) -> None:
        for agent in self.trailing_agents:
            agent.stop_trailing(reason)

    def remove_guarding_agents(self, ) -> None:
        for agent in self.guarding_agents:
            agent.stop_guarding()

    def reached_end_of_route(self) -> None:
        """
        Set of instructions to follow once the end of agent route is reached.
        Not provided on Agent level
        :return:
        """
        raise NotImplementedError(f"Reach end of route function not implemented for standard AGENT type.")

    def make_move(self):
        self.distance_to_travel = self.speed * constants.world.time_delta
        self.move()
        self.update_plot()

    def move(self, distance_to_travel=None):
        """
        Module to make move for the current timestep
        Not implemented on AGENT level.
        :return:
        """
        raise NotImplementedError("Move functionality not implemented on AGENT level")

    def move_through_route(self, distance_to_travel=None) -> None:
        """
        Move the agent through their current provided route.
        :param distance_to_travel: Distance to travel during this timestep
        :return: remaining distance to travel
        """
        if distance_to_travel is not None:
            self.distance_to_travel = distance_to_travel

        iterations = 0
        while self.distance_to_travel > 0:
            iterations += 1
            if iterations > constants.ITERATION_LIMIT:
                if self.route is not None:
                    logger.warning(f"Route: {[str(p) for p in self.route.points]}")
                    self.next_point.add_point_to_plot(constants.axes_plot, color="yellow", text="next")
                self.location.add_point_to_plot(constants.axes_plot, color="yellow", text="L")
                raise TimeoutError(f"Distance travel not converging for agent")

            # Instance 1: Staying close to a tracked agent
            if (self.trailing and calculate_distance(a=self.location,
                                                     b=self.located_agent.location) < constants.MAX_TRAILING_DISTANCE):
                # If we are close enough, we trail instead of getting closer.
                return

            # Instance 2: Move through the route
            if self.next_point is not None:
                distance_to_next_point = self.location.distance_to_point(self.next_point)

                distance_travelled = min(self.distance_to_travel, distance_to_next_point)
                self.distance_to_travel -= distance_travelled

                # Instance 2.1: We can reach the next point
                if distance_to_next_point <= distance_travelled:
                    self.last_location = self.next_point
                    self.past_points.append(self.next_point)
                    self.location = copy.deepcopy(self.next_point)

                    # Instance 2.1a: Reached point, getting ready for next point
                    if len(self.remaining_points) > 0:
                        self.next_point = self.remaining_points.pop(0)

                    # Instance 2.1b: Reached point, was final point on route
                    else:
                        self.reached_end_of_route()
                        if constants.DEBUG_MODE:
                            self.debug()
                        return

                # Instance 2.2: We travel towards the next point but do not reach it
                else:
                    # TODO: Improve LON/LAT movement approximation
                    part_of_route = (distance_travelled / distance_to_next_point)
                    new_x = self.location.x + part_of_route * (self.next_point.x - self.location.x)
                    new_y = self.location.y + part_of_route * (self.next_point.y - self.location.y)
                    self.location = Point(new_x, new_y, name=str(self))

                    if constants.DEBUG_MODE:
                        self.debug()
                    return

    def can_continue(self) -> bool:
        """
        See if Agent can continue current actions or has to return to resupply
        :return:
        """
        remaining_endurance = self.endurance - self.time_spent_from_base

        # Check heuristically - to prevent route creation for all instances
        dist_to_base = self.location.distance_to_point(self.base.location)
        required_endurance_max = (1.5 * dist_to_base) / self.speed
        if required_endurance_max < remaining_endurance:
            return True

        base_route = create_route(self.location, self.base.location, self.obstacles)
        time_required_to_return = np.ceil(base_route.length / self.speed)
        if remaining_endurance * (1 + constants.SAFETY_ENDURANCE) <= time_required_to_return:
            self.return_to_base()
        else:
            return True

    def is_near(self, location: Point = None, agent=None) -> bool:
        """
        See if a location or agent is close to this object
        :param agent:
        :param location:
        :return:
        """
        if location is None:
            if agent is None:
                raise ValueError("No location nor agent provided for is_near function.")
            else:
                location = agent.location

        if self.location.distance_to_point(location) < constants.MAX_TRAILING_DISTANCE:
            return True
        else:
            return False

    def return_to_base(self) -> None:
        """
        Function to return agent to base.
        Not defined on AGENT level.
        :return:
        """
        raise NotImplementedError(f"Return to base function not implemented for standard AGENT type.")

    def start_maintenance(self) -> None:
        self.time_spent_from_base = 0
        self.remaining_maintenance_time = self.maintenance_time
        self.base.maintenance_queue.append(self)

    def complete_maintenance(self):
        raise NotImplementedError("No maintenance completion on AGENT level.")

    def call_action_on_agent(self):
        """
        The agent will take action on the trailed object, either engaging the object itself, or calling in support.
        :return:
        """
        if self.ammunition > 0:
            self.engage_agent()
        elif not self.awaiting_support:
            self.call_in_support()

    def reach_and_return(self, target) -> bool:
        """
        Test if agent can travel to the target location and still return to base before endurance runs out.
        :param target: Goal location to reach
        :return:
        """
        # First check if the distance is possible without obstacles to prevent unnecessary heavier computations
        remaining_endurance = self.endurance - self.time_spent_from_base
        dist_to_point = self.location.distance_to_point(target)
        dist_to_base = target.distance_to_point(self.base.location)
        min_endurance_required = (dist_to_point + dist_to_base) / self.speed

        if min_endurance_required * (1 + constants.SAFETY_ENDURANCE) > remaining_endurance:
            return False

        # logger.debug(f"Checking if UAV {self.uav_id} can reach {target} and return to {self.base.location}")
        path_to_point = create_route(self.location, target, polygons_to_avoid=self.obstacles)
        path_to_base = create_route(target, self.base.location, polygons_to_avoid=self.obstacles)
        total_length = path_to_point.length + path_to_base.length
        endurance_required = total_length / self.speed
        # See if we have enough endurance remaining, plus small penalty to ensure we can trail
        if endurance_required * (1 + constants.SAFETY_ENDURANCE) < remaining_endurance:
            return True
        else:
            return False

    def move_towards_orientation(self, distance_to_travel: float, direction=None) -> Point:
        """
        Used to explore move in POTENTIAL direction to calculate pay-off for patrolling options
        :param distance_to_travel: Distance to travel in KM
        :param direction: N/E/S/W direction
        :return: New point of arrival
        """
        x, y = self.location.location()

        if direction is None:
            direction = self.direction

        latitudinal_distance = distance_to_travel / constants.LATITUDE_CONVERSION_FACTOR
        latitude = self.location.y
        longitudinal_distance = distance_to_travel / (constants.LONGITUDE_CONVERSION_FACTOR
                                                      * math.cos(math.radians(latitude)))
        if direction == "north":
            return Point(x, y + latitudinal_distance)
        elif direction == "east":
            return Point(x + longitudinal_distance, y)
        elif direction == "south":
            return Point(x, y - latitudinal_distance)
        elif direction == "west":
            return Point(x - longitudinal_distance, y)
        elif direction == "reverse":
            if self.direction == "north":
                return Point(x, y - latitudinal_distance)
            elif self.direction == "east":
                return Point(x - longitudinal_distance, y)
            elif self.direction == "south":
                return Point(x, y + latitudinal_distance)
            elif self.direction == "west":
                return Point(x + longitudinal_distance, y)
            else:
                raise NotImplementedError(f"Invalid direction {self.direction}")
        else:
            raise ValueError(f"Invalid direction {direction}")

    def make_next_patrol_move(self):
        self.last_location = self.location
        distance_to_travel = self.distance_to_travel
        self.distance_to_travel = 0

        if self.direction == "north":
            left_direction = "west"
            right_direction = "east"
            turn_direction = "south"
        elif self.direction == "east":
            left_direction = "north"
            right_direction = "south"
            turn_direction = "west"
        elif self.direction == "south":
            left_direction = "east"
            right_direction = "west"
            turn_direction = "north"
        elif self.direction == "west":
            left_direction = "south"
            right_direction = "north"
            turn_direction = "east"
        else:
            raise ValueError(f"Unexpected direction {self.direction}")

        left_point = self.move_towards_orientation(distance_to_travel, direction=left_direction)
        CoP_left, left_receptors = constants.world.receptor_grid.calculate_CoP(left_point, self.radius)

        straight_point = self.move_towards_orientation(distance_to_travel, direction=self.direction)
        CoP_straight, straight_receptors = constants.world.receptor_grid.calculate_CoP(straight_point, self.radius)

        right_point = self.move_towards_orientation(distance_to_travel, direction=right_direction)
        CoP_right, right_receptors = constants.world.receptor_grid.calculate_CoP(right_point, self.radius)

        # logger.debug(f"{CoP_left=}, {CoP_straight=}, {CoP_right=}")
        concentration_of_pheromones = [CoP_left, CoP_straight, CoP_right]
        try:
            probabilities = [1 / CoP for CoP in concentration_of_pheromones]
        except ZeroDivisionError:
            logger.warning(f"Agent {self} at {self.location.x}, {self.location.y} has 0 CoP surrounding.")
            probabilities = [1 / 3, 1 / 3, 1 / 3]
        if sum(probabilities) != 0:
            probabilities = [p / sum(probabilities) for p in probabilities]
        else:
            logger.warning(f"No Valid probabilities")
            probabilities = [1 / len(probabilities)] * len(probabilities)

        if all([math.isinf(CoP_left), math.isinf(CoP_straight), math.isinf(CoP_right)]):
            direction = "turn"
        else:
            if constants.DEBUG_MODE:
                if any(np.isnan(probabilities)):
                    self.location.add_point_to_plot(constants.axes_plot, color="purple")
                    left_point.add_point_to_plot(constants.axes_plot, color="blue")
                    straight_point.add_point_to_plot(constants.axes_plot, color="red")
                    right_point.add_point_to_plot(constants.axes_plot, color="green")
                    raise ValueError(f"Probability is NaN - agent {self} at "
                                     f"({self.location.x}, {self.location.y}).\n"
                                     f"({left_point.x}, {left_point.y}), "
                                     f"({straight_point.x}, {straight_point.y})"
                                     f",({right_point.x}, {right_point.y}) - {probabilities}")

            direction = np.random.choice(["left", "straight", "right"], 1, p=probabilities)

        if direction == "left":
            new_location = left_point
            self.direction = left_direction
        elif direction == "straight":
            new_location = straight_point
        elif direction == "right":
            new_location = right_point
            self.direction = right_direction
        else:
            new_location = self.move_towards_orientation(distance_to_travel, direction=turn_direction)
            self.direction = turn_direction

        self.location = copy.deepcopy(new_location)
        self.location.name = f"Agent {self}"

        # Check if drone is in legal location
        if constants.DEBUG_MODE:
            self.debug()

        self.observe_area()
        self.spread_pheromones()

    def observe_area(self):
        """
        Function for the agent to observe the area and detect other unknown agents.
        :return:
        """
        raise NotImplementedError("Observe area not available on AGENT level")

    def spread_pheromones(self):
        """
        Make the agent spread pheromones in their area
        :return:
        """
        locations = []
        for lamb in np.arange(0, 1, 1 / constants.world.splits_per_step):
            x_loc = self.location.x * lamb + self.last_location.x * (1 - lamb)
            y_loc = self.location.y * lamb + self.last_location.y * (1 - lamb)
            locations.append(Point(x_loc, y_loc))

        for location in locations:
            receptors = constants.world.receptor_grid.select_receptors_in_radius(
                location, radius=self.radius * constants.LATITUDE_CONVERSION_FACTOR)

            for receptor in receptors:
                if receptor.decay:  # To Check if receptor is not a boundary point
                    if self.pheromone_type == "alpha":
                        receptor.alpha_pheromones += ((1 / max(location.distance_to_point(receptor.location), 0.1)) *
                                                      (self.pheromone_spread / constants.world.splits_per_step))
                    elif self.pheromone_type == "beta":
                        receptor.beta_pheromones += ((1 / max(location.distance_to_point(receptor.location), 0.1)) *
                                                     (self.pheromone_spread / constants.world.splits_per_step))
                    # receptor.update_plot(self.world.ax, self.world.receptor_grid.cmap)

    def engage_agent(self):
        """
        Take action on another agent - Either attack, board, or different.
        Not implemented on an AGENT level.
        :return:
        """
        raise NotImplementedError("No attack protocol for base object AGENT")

    def call_in_support(self):
        """
        Call in another agent or object to take action onto the agent being trailed.
        Not implemented on an AGENT level.
        :return:
        """
        raise NotImplementedError("No support protocol for base object AGENT")

    def start_retreat(self) -> None:
        """
        Start retreat process, generate a route back out of the area of interest
        :return:
        """
        print(f"{self} is retreating with {self.health_points=}")
        if self.routing_to_base:
            return
        else:
            self.routing_to_base = True
            self.generate_route(destination=self.base)

    def remove_from_plot(self):
        if not constants.PLOTTING_MODE:
            return
        if self.marker is not None:
            for m in self.marker:
                m.remove()
            self.text.remove()
            self.marker = None

        if self.radius_patch is not None:
            self.radius_patch.remove()
            self.radius_patch = None

        if constants.DEBUG_MODE:
            if self.route_plot is not None:
                for lines in self.route_plot:
                    line = lines.pop(0)
                    line.remove()
                self.route_plot = None

    def update_plot(self) -> None:
        if not constants.PLOTTING_MODE:
            return

        self.remove_from_plot()

        if self.stationed or self.left_world:
            return

        # Re-add new plots
        if constants.DEBUG_MODE and self.route is not None:
            remaining_route = Route(points=([self.location] + [self.next_point] + self.remaining_points))
            self.route_plot = remaining_route.add_route_to_plot(constants.axes_plot, color=self.color)
            # self.route_plot = self.route.add_route_to_plot(constants.axes_plot)

        self.radius_patch = matplotlib.patches.Circle((self.location.x, self.location.y),
                                                      radius=self.radius / constants.LATITUDE_CONVERSION_FACTOR,
                                                      color=self.color, alpha=0.1, linewidth=None)

        constants.world.ax.add_patch(self.radius_patch)
        self.marker = constants.world.ax.plot(self.location.x, self.location.y, color=self.color,
                                              marker="X", markersize=constants.WORLD_MARKER_SIZE - 1,
                                              markeredgecolor="black")

        self.text = constants.world.ax.text(self.location.x, self.location.y - 0.001, s=str(self), color="white")

    def debug(self) -> None:
        """
        Checks if any rules and/or logic are violated
        :return:
        """
        for polygon in self.obstacles:
            if polygon.check_if_contains_point(P=self.location, exclude_edges=True):
                self.location.add_point_to_plot(axes=constants.axes_plot, color="yellow")
                if self.last_location is not None:
                    self.last_location.add_point_to_plot(axes=constants.axes_plot, color="purple", text="LAST")
                self.next_point.add_point_to_plot(axes=constants.axes_plot, color="red", text="NEXT")

                if self.located_agent is not None:
                    self.located_agent.location.add_point_to_plot(axes=constants.axes_plot,
                                                                  color="green", text="Current")
                    self.located_agent.next_point.add_point_to_plot(axes=constants.axes_plot,
                                                                    color="green", text="Next")
                    self.located_agent.past_points[-1].add_point_to_plot(axes=constants.axes_plot,
                                                                         color="green", text="Last")

                for p in self.past_points:
                    p.add_point_to_plot(axes=constants.axes_plot, color="black", text=p.point_id)
                if self.route is not None:
                    self.route.add_route_to_plot(axes=constants.axes_plot)
                raise PermissionError(f"Agent {self} at illegal location: \n"
                                      f"({self.location.x: .3f}, {self.location.y: .3f}). \n"
                                      f"Route is {[str(p) for p in self.route.points]} \n"
                                      f"Routing to base: {self.routing_to_base} \n"
                                      f"Stationed? {self.stationed} \n"
                                      f"next point: {self.next_point} \n"
                                      f"last point: {self.last_location} \n"
                                      f"trailing? : {self.trailing}. \n"
                                      f"Last location = ({self.last_location.x}, {self.last_location.y}). \n"
                                      f"this falls in polygon {[str(p) for p in polygon.points]}")
