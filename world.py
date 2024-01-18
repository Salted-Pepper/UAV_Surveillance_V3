"""
Ties all the agents together for a single simulation and collects the data.
A world has a set time delta, which sets the time-jumps per simulation step.
A time delta of 1 corresponds to jumps of 1 hour real time.
"""

import datetime
import logging
from logging.handlers import RotatingFileHandler
import os
import time

import weather_data

if not os.path.exists("logs"):
    os.makedirs("logs")

import matplotlib.pyplot as plt
import numpy as np

import constants
import constants_coords
from polygons import Polygon
from receptors import ReceptorGrid
from managers import MerchantManager, USManager, TaiwanManager, JapanManager, UAVManager

date = datetime.date.today()

logging.basicConfig(level=logging.DEBUG, filename=os.path.join(os.getcwd(), 'logs/navy_log_' + str(date) + '.log'),
                    handlers=[RotatingFileHandler("logs/navy_log_" + str(date) + ".log",
                                                  maxBytes=2000, backupCount=10)],
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt="%H:%M:%S", filemode='w')
logger = logging.getLogger("WORLD")
logger.setLevel(logging.DEBUG)

logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)
logging.getLogger("fiona.ogrext").setLevel(logging.WARNING)
logging.getLogger("GEOPOLYGON").setLevel(logging.WARNING)


class World:
    def __init__(self, time_delta: float):
        constants.world = self
        # timer functions
        self.time_spent_on_UAVs = 0
        self.time_spent_on_merchants = 0
        self.time_spent_plotting = 0

        # Create Geography
        self.landmasses = []
        self.china_polygon = None
        self.initiate_land_masses()

        self.x_min = None
        self.x_max = None

        self.y_min = None
        self.y_max = None

        self.managers = None
        self.initiate_managers()

        self.receptor_grid = None
        self.initiate_receptor_grid()

        # World Variable Characteristics
        self.weather = None
        self.time_last_weather_update = 0
        self.time_delta = time_delta  # In Hours
        # Usage of more detailed splits for instances of accuracy
        self.splits_per_step = int(np.ceil(constants.UAV_MOVEMENT_SPLITS_P_H * self.time_delta))
        print(f"SPLITS PER TIME DELTA SET AT {self.splits_per_step}")
        self.world_time = 0

        # Statistics
        self.current_vessels = []
        self.current_airborne_drones = []

        # Plotting
        self.fig = None
        self.ax = None
        self.plot_world(True)

    def initiate_land_masses(self) -> None:
        self.landmasses = [Polygon(name="taiwan", points=constants_coords.TAIWAN_POINTS,
                                   color=constants_coords.TAIWAN_COLOR),
                           Polygon(name="orchid_island", points=constants_coords.ORCHID_ISLAND_POINTS,
                                   color=constants_coords.TAIWAN_COLOR),
                           Polygon(name="green_island", points=constants_coords.GREEN_ISLAND_POINTS,
                                   color=constants_coords.TAIWAN_COLOR),
                           Polygon(name="penghu", points=constants_coords.PENGHU_COUNTRY_POINTS,
                                   color=constants_coords.TAIWAN_COLOR),
                           Polygon(name="wangan", points=constants_coords.WANGAN_POINTS,
                                   color=constants_coords.TAIWAN_COLOR),
                           Polygon(name="qimei", points=constants_coords.QIMEI_POINTS,
                                   color=constants_coords.TAIWAN_COLOR),
                           Polygon(name="yonaguni", points=constants_coords.YONAGUNI_POINTS,
                                   color=constants_coords.JAPAN_COLOR),
                           Polygon(name="taketomi", points=constants_coords.TAKETOMI_POINTS,
                                   color=constants_coords.JAPAN_COLOR),
                           Polygon(name="ishigaki", points=constants_coords.ISHIGAKE_POINTS,
                                   color=constants_coords.JAPAN_COLOR),
                           Polygon(name="miyakojima", points=constants_coords.MIYAKOJIMA_POINTS,
                                   color=constants_coords.JAPAN_COLOR),
                           Polygon(name="okinawa", points=constants_coords.OKINAWA_POINTS,
                                   color=constants_coords.JAPAN_COLOR),
                           Polygon(name="okinoerabujima",
                                   points=constants_coords.OKINOERABUJIMA_POINTS,
                                   color=constants_coords.JAPAN_COLOR),
                           Polygon(name="tokunoshima", points=constants_coords.TOKUNOSHIMA_POINTS,
                                   color=constants_coords.JAPAN_COLOR),
                           Polygon(name="amami_oshima", points=constants_coords.AMAMI_OSHIMA_POINTS,
                                   color=constants_coords.JAPAN_COLOR),
                           Polygon(name="yakushima", points=constants_coords.YAKUSHIMA_POINTS,
                                   color=constants_coords.JAPAN_COLOR),
                           Polygon(name="tanegashima", points=constants_coords.TANEGASHIMA_POINTS,
                                   color=constants_coords.JAPAN_COLOR),
                           Polygon(name="japan", points=constants_coords.JAPAN_POINTS,
                                   color=constants_coords.JAPAN_COLOR),
                           ]

        self.china_polygon = Polygon(name="china", points=constants_coords.CHINA_POINTS,
                                     color=constants_coords.CHINA_COLOR)

    def initiate_receptor_grid(self) -> None:
        self.receptor_grid = ReceptorGrid(self.landmasses + [self.china_polygon], self)

    def initiate_managers(self) -> None:
        self.managers = [UAVManager(),
                         MerchantManager(),
                         USManager(),
                         TaiwanManager(),
                         JapanManager(),
                         ]

    def plot_world(self, include_receptors=False) -> None:
        if not constants.PLOTTING_MODE and not constants.DEBUG_MODE:
            return
        self.fig, self.ax = plt.subplots(1, figsize=(constants.PLOT_SIZE, constants.PLOT_SIZE))
        constants.axes_plot = self.ax
        self.ax.set_title(f"Sea Map - time is {self.world_time}")
        self.ax.set_facecolor("#2596be")
        self.ax.set_xlim(left=constants.MIN_LAT, right=constants.MAX_LAT)
        self.ax.set_xlabel("Latitude")
        self.ax.set_ylim(bottom=constants.MIN_LONG, top=constants.MAX_LONG)
        self.ax.set_ylabel("Longitude")

        for landmass in self.landmasses:
            logging.debug(f"Plotting {landmass}")
            self.ax = landmass.add_polygon_to_plot(self.ax)

        self.ax = self.china_polygon.add_polygon_to_plot(self.ax)

        for manager in self.managers:
            for base in manager.bases:
                base.add_to_plot()

        if include_receptors:
            for receptor in self.receptor_grid.receptors:
                self.ax = receptor.initiate_plot(self.ax, self.receptor_grid.cmap)

        plt.show()
        self.fig.canvas.draw()

    def plot_world_update(self) -> None:
        if not constants.PLOTTING_MODE:
            return

        self.ax.set_title(f"Sea Map - time is {self.world_time: .3f}")

        for receptor in self.receptor_grid.receptors:
            receptor.update_plot(self.ax, self.receptor_grid.cmap)

        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        plt.show()

    def time_step(self) -> None:
        print(f"Starting iteration {self.world_time: .3f}")
        self.world_time += self.time_delta

        self.update_weather_conditions()

        for management in self.managers:
            logger.debug(f"{management} is working...")
            management.manage_agents()

        t_0 = time.perf_counter()
        self.receptor_grid.depreciate_pheromones()
        t_1 = time.perf_counter()
        constants.time_spent_depreciating_pheromones += (t_1 - t_0)

        t_0 = time.perf_counter()
        self.plot_world_update()
        t_1 = time.perf_counter()
        self.time_spent_plotting += (t_1 - t_0)

        logger.debug(f"End of iteration {self.world_time: .3f} \n")

    def update_weather_conditions(self):
        """
        Updates the weather and samples sea states pending.
        :return:
        """
        if self.world_time - self.time_last_weather_update > constants.WEATHER_RESAMPLING_TIME_SPLIT:
            print(f"UPDATING SEA STATES")
            self.time_last_weather_update = self.world_time
            weather_data.update_sea_states(self)
            return


if __name__ == "__main__":
    t_0 = time.perf_counter()
    world = World(time_delta=0.2)

    for z in range(10000):
        world.time_step()

    t_1 = time.perf_counter()

    print(f"TOTAL TIME: {(t_1 - t_0) / 60} \n"
          f"Time spent on Merchants: {world.time_spent_on_merchants / 60} \n"
          f"Time spent on UAVs: {world.time_spent_on_UAVs / 60} \n"
          f"Time spent deprecating pheromones: {constants.time_spent_depreciating_pheromones / 60} \n"
          f"Time spent plotting: {world.time_spent_plotting / 60} \n")
    print(f"Time spent on: \n"
          f"Creating routes: {constants.time_spent_creating_routes / 60} \n"
          f"Calculating distance: {constants.time_spent_calculating_distance / 60} \n"
          f"Making Patrol Moves: {constants.time_spent_making_patrol_moves / 60} \n"
          f"Spreading Pheromones: {constants.time_spreading_pheromones / 60} \n"
          f"Updating Route: {constants.time_spent_updating_trail_route / 60} \n"
          f"UAV Moving through route: {constants.time_spent_uav_route_move / 60} \n"
          f"UAV return checks: {constants.time_spent_checking_uav_return / 60} \n"
          f"Following Routes: {constants.time_spent_following_route / 60} \n"
          f"Launching Drones: {constants.time_spent_launching_drones / 60} \n"
          f"Observing Area: {constants.time_spent_observing_area / 60} \n")
