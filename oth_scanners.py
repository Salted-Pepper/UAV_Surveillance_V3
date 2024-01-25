import random
import math
from general_maths import calculate_direction_vector

import constants
from points import Point
from polygons import Polygon
from ships import Merchant


class OTH:
    def __init__(self, location: Point, direction_point: Point):
        self.team = 2
        self.location = location
        self.direction = None
        self.normalize_direction(direction_point)

        # Degree of the
        self.angle = 45
        # Save degrees and sines/cosines to prevent redoing calculations consistently
        self.pos_cos = math.cos(self.angle)
        self.pos_sin = math.sin(self.angle)
        self.neg_cos = math.cos(-self.angle)
        self.neg_sin = math.sin(-self.angle)

        self.active = False

        # Scanning parameters
        self.range_band = 30
        self.scan_time = 1 / 60  # Scan one bandwidth per minute

        self.min_band = 700
        self.max_band = 3500

        self.current_band = self.min_band

        self.scanned_polygon = None
        self.range_band_plot = None

    def normalize_direction(self, direction_point):
        """
        Ensure that the direction of the OTH is a normalized position.
        :return:
        """
        self.direction = calculate_direction_vector(self.location, direction_point)

    @staticmethod
    def detected_agent(agent) -> bool:

        receptor = constants.world.receptor_grid.get_closest_receptor(agent.location)
        sea_state = receptor.sea_state
        detected = False

        # TODO: See if detection is based on RCS or cargo load
        #  and detection of non-merchant agents?

        if isinstance(agent, Merchant):
            if sea_state <= 1:
                detected = True
            elif sea_state == 2 and agent.cargo_load >= 500:
                detected = True
            elif sea_state == 3 and agent.cargo_load >= 1200:
                detected = True
            elif sea_state == 4 and agent.cargo_load >= 10_000:
                detected = True
            elif sea_state == 5 and agent.cargo_load >= 100_000:
                detected = True

        return detected

    def check_scan_area(self) -> None:
        min_range = self.current_band
        max_range = self.current_band + (constants.world.time_delta / self.scan_time) * self.range_band

        if max_range > self.max_band:
            max_range = self.max_band
            self.current_band = min_range
        else:
            self.current_band = max_range

        agents_to_check = [agent
                           for manager in constants.world.managers
                           if manager.team != self.team
                           for agent in manager.agents]

        self.scanned_polygon = self.calculate_scanned_polygon(min_range, max_range)

        located_agents = []
        for agent in agents_to_check:
            self.scanned_polygon.check_if_contains_point(agent.location)
            if self.detected_agent(agent):
                located_agents.append(agent)

    def calculate_scanned_polygon(self, min_range: float, max_range: float) -> Polygon:
        """
        Calculate the polygon that is evaluated at the current timestep.
        :param min_range: Minimal bandwidth for the current timestep
        :param max_range: Maximum bandwidth for the current timestep
        :return:
        """
        direction_vector_x_min = self.location.x + self.direction[0] * min_range
        direction_vector_y_min = self.location.y + self.direction[1] * min_range

        direction_vector_x_max = self.location.x + self.direction[0] * max_range
        direction_vector_y_max = self.location.y + self.direction[1] * max_range

        low_min = Point(self.neg_cos*direction_vector_x_min - self.neg_sin*direction_vector_y_min,
                        self.neg_sin*direction_vector_x_min + self.neg_cos*direction_vector_y_min)
        high_min = Point(self.pos_cos*direction_vector_x_min - self.pos_sin*direction_vector_y_min,
                         self.pos_sin*direction_vector_x_min + self.pos_cos*direction_vector_y_min)
        low_max = Point(self.neg_cos*direction_vector_x_max - self.neg_sin*direction_vector_y_max,
                        self.neg_sin*direction_vector_x_max + self.neg_cos*direction_vector_y_max)
        high_max = Point(self.pos_cos*direction_vector_x_max - self.pos_sin*direction_vector_y_max,
                         self.pos_sin*direction_vector_x_max + self.pos_cos*direction_vector_y_max)

        return Polygon(points=[low_min, high_min, low_max, high_max],
                       color="salmon")

    def roll_if_active(self, time: str) -> None:
        """
        Check if the OTH is active or not for the upcoming 12h block.
        Checks are done at 7am and 7pm world time.

        At 7am, 5% that conditions are too bad - no checks
        At 7pm, 50% chance that no OTH checks are made
        :param time: String either 'AM' or 'PM'
        :return:
        """
        random_value = random.uniform(0, 1)

        if time == "AM":
            if random_value <= 0.05:
                self.active = False
            else:
                self.active = True
        elif time == "PM":
            if random_value <= 0.5:
                self.active = False
            else:
                self.active = True
        else:
            raise NotImplementedError(f"Time {time} not implemented.")
        pass

    def remove_from_plot(self) -> None:
        if not constants.PLOTTING_MODE:
            return

        if self.range_band_plot is not None:
            self.range_band_plot.remove()

    def plot_range_band(self) -> None:
        if not constants.PLOTTING_MODE:
            return

        self.remove_from_plot()

        if self.scanned_polygon is not None:
            self.range_band_plot = self.scanned_polygon.add_polygon_to_plot(constants.axes_plot, opacity=0.3)
