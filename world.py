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

import model_info
import constants
import constants_coords
from drones import Drone, DroneType
from points import Point
from polygons import Polygon
from receptors import ReceptorGrid
from ships import Ship, Merchant, generate_random_merchant
from base import Harbour, Airbase
from managers import

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
        # timer functions
        self.time_spent_on_UAVs = 0
        self.time_spent_on_merchants = 0
        self.time_spent_plotting = 0

        # Create Geography
        self.landmasses = []
        self.china_polygon = None
        self.initiate_land_masses()
        self.polygons = [landmass.polygon for landmass in self.landmasses]

        self.x_min = None
        self.x_max = None

        self.y_min = None
        self.y_max = None

        self.escort_management = None
        self.initiate_escort_management()

        self.docks = None
        self.initiate_docks()

        self.airbases = None
        self.initiate_airbases()

        self.receptor_grid = None
        self.initiate_receptor_grid()

        # World Variable Characteristics
        self.weather = None
        self.time_last_weather_update = 0
        self.wind_direction = "East"  # Direction wind is COMING from
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

        self.drones = []
        self.drone_types = []
        self.initiate_drones()

    def initiate_land_masses(self) -> None:
        self.landmasses = [Landmass(name="taiwan", polygon=Polygon(points=constants_coords.TAIWAN_POINTS),
                                    color=constants_coords.TAIWAN_COLOR),
                           Landmass(name="orchid_island", polygon=Polygon(points=constants_coords.ORCHID_ISLAND_POINTS),
                                    color=constants_coords.TAIWAN_COLOR),
                           Landmass(name="green_island", polygon=Polygon(points=constants_coords.GREEN_ISLAND_POINTS),
                                    color=constants_coords.TAIWAN_COLOR),
                           Landmass(name="penghu", polygon=Polygon(points=constants_coords.PENGHU_COUNTRY_POINTS),
                                    color=constants_coords.TAIWAN_COLOR),
                           Landmass(name="wangan", polygon=Polygon(points=constants_coords.WANGAN_POINTS),
                                    color=constants_coords.TAIWAN_COLOR),
                           Landmass(name="qimei", polygon=Polygon(points=constants_coords.QIMEI_POINTS),
                                    color=constants_coords.TAIWAN_COLOR),
                           Landmass(name="yonaguni", polygon=Polygon(points=constants_coords.YONAGUNI_POINTS),
                                    color=constants_coords.JAPAN_COLOR),
                           Landmass(name="taketomi", polygon=Polygon(points=constants_coords.TAKETOMI_POINTS),
                                    color=constants_coords.JAPAN_COLOR),
                           Landmass(name="ishigaki", polygon=Polygon(points=constants_coords.ISHIGAKE_POINTS),
                                    color=constants_coords.JAPAN_COLOR),
                           Landmass(name="miyakojima", polygon=Polygon(points=constants_coords.MIYAKOJIMA_POINTS),
                                    color=constants_coords.JAPAN_COLOR),
                           Landmass(name="okinawa", polygon=Polygon(points=constants_coords.OKINAWA_POINTS),
                                    color=constants_coords.JAPAN_COLOR),
                           Landmass(name="okinoerabujima",
                                    polygon=Polygon(points=constants_coords.OKINOERABUJIMA_POINTS),
                                    color=constants_coords.JAPAN_COLOR),
                           Landmass(name="tokunoshima", polygon=Polygon(points=constants_coords.TOKUNOSHIMA_POINTS),
                                    color=constants_coords.JAPAN_COLOR),
                           Landmass(name="amami_oshima", polygon=Polygon(points=constants_coords.AMAMI_OSHIMA_POINTS),
                                    color=constants_coords.JAPAN_COLOR),
                           Landmass(name="yakushima", polygon=Polygon(points=constants_coords.YAKUSHIMA_POINTS),
                                    color=constants_coords.JAPAN_COLOR),
                           Landmass(name="tanegashima", polygon=Polygon(points=constants_coords.TANEGASHIMA_POINTS),
                                    color=constants_coords.JAPAN_COLOR),
                           Landmass(name="japan", polygon=Polygon(points=constants_coords.JAPAN_POINTS),
                                    color=constants_coords.JAPAN_COLOR),
                           ]

        self.china_polygon = Landmass(name="china", polygon=Polygon(points=constants_coords.CHINA_POINTS),
                                      color=constants_coords.CHINA_COLOR)

    def initiate_receptor_grid(self) -> None:
        self.receptor_grid = ReceptorGrid(self.polygons + [self.china_polygon.polygon], self)

    def initiate_escort_management(self) -> None:
        self.escort_management = [EscortManagement(self, country="US"),
                                  EscortManagement(self, country="Taiwan"),
                                  EscortManagement(self, country="Japan"),
                                  ]

    def initiate_docks(self) -> None:
        self.docks = [Harbour(name="Kaohsiung", location=Point(120.30, 22.44,
                                                               name="Kaohsiung", force_maintain=True)),
                      Harbour(name="Tiachung", location=Point(120.42, 24.21,
                                                              name="Tiachung", force_maintain=True)),
                      Harbour(name="Keelung", location=Point(121.75, 25.19,
                                                             name="Keelung", force_maintain=True)),
                      Harbour(name="Hualien", location=Point(121.70, 23.96,
                                                             name="Hualien", force_maintain=True))]

    def initiate_airbases(self) -> None:
        self.airbases = [Airbase(name="Ningbo", location=Point(121.57, 29.92,
                                                               force_maintain=True, name="Ningbo")),
                         Airbase(name="Fuzhou", location=Point(119.31, 26.00,
                                                               force_maintain=True, name="Fuzhou")),
                         Airbase(name="Liangcheng", location=Point(116.75, 25.68,
                                                                   force_maintain=True, name="Liangcheng")),
                         ]

    def initiate_drones(self) -> None:
        # TODO: Distribute drones equally over airbases
        logger.debug("Initiating Drones...")

        for model in model_info.UAV_MODELS:
            drone_type = DroneType(name=model['name'],
                                   amount=np.floor(model['number_of_airframes'] * constants.UAV_AVAILABILITY))
            self.drone_types.append(drone_type)

            for _ in range(model['number_of_airframes']):
                new_drone = Drone(model=model['name'], drone_type=drone_type,
                                  base=np.random.choice(self.airbases))
                self.drones.append(new_drone)
                drone_type.drones.append(new_drone)

            drone_type.calculate_utilization_rate()

    def plot_world(self, include_receptors=False) -> None:
        if not constants.PLOTTING_MODE and not constants.DEBUG_MODE:
            return
        self.fig, self.ax = plt.subplots(1, figsize=(constants.PLOT_SIZE, constants.PLOT_SIZE))
        self.ax.set_title(f"Sea Map - time is {self.world_time}")
        self.ax.set_facecolor("#2596be")
        self.ax.set_xlim(left=constants.MIN_LAT, right=constants.MAX_LAT)
        self.ax.set_xlabel("Latitude")
        self.ax.set_ylim(bottom=constants.MIN_LONG, top=constants.MAX_LONG)
        self.ax.set_ylabel("Longitude")

        for landmass in self.landmasses:
            logging.debug(f"Plotting {landmass}")
            self.ax = landmass.add_landmass_to_plot(self.ax)

        self.ax = self.china_polygon.add_landmass_to_plot(self.ax)

        for dock in self.docks:
            logging.debug(f"Plotting {dock}")
            self.ax = dock.add_dock_to_plot(self.ax)

        for airbase in self.airbases:
            logging.debug(f"Plotting {airbase}")
            self.ax = airbase.add_airbase_to_plot(self.ax)

        if include_receptors:
            for receptor in self.receptor_grid.receptors:
                self.ax = receptor.initiate_plot(self.ax, self.receptor_grid.cmap)
        constants.axes_plot = self.ax

        plt.show()
        self.fig.canvas.draw()

    def plot_world_update(self) -> None:
        if not constants.PLOTTING_MODE:
            return

        self.ax.set_title(f"Sea Map - time is {self.world_time: .3f}")
        for ship in self.current_vessels:
            ship.update_plot()

        for drone in self.current_airborne_drones:
            drone.update_plot()

        for receptor in self.receptor_grid.receptors:
            receptor.update_plot(self.ax, self.receptor_grid.cmap)

        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        plt.show()

    def merchant_enters(self, merchant: Merchant) -> None:
        merchant.enter_world(self)
        self.current_vessels.append(merchant)

    def launch_drone(self) -> None:
        t_0 = time.perf_counter()
        for drone_type in self.drone_types:
            if not drone_type.reached_utilization_rate():
                drone_type.launch_drone_of_type(self)
        t_1 = time.perf_counter()
        constants.time_spent_launching_drones += (t_1 - t_0)

    def calculate_ships_entering(self) -> int:
        """
        Calculate number of ships entering in time period t.
        :return: Integer number of ships entering
        """
        # TODO: Sample from poisson with rate lambda as in overleaf
        if np.random.rand() > 0.99:
            return 1
        else:
            return 0

    def create_arriving_merchants(self) -> None:
        for _ in range(self.calculate_ships_entering()):
            new_merchant = generate_random_merchant(self)
            logger.debug(f"New ship: {new_merchant.ship_id} is entering the AoI")
            self.merchant_enters(new_merchant)

    def calculate_ship_movements(self) -> None:
        ships_finished = []

        for ship in self.current_vessels:
            ship.make_move()
            if ship.left_world:
                ships_finished.append(ship)

        # Remove ships that have reached their destination
        for ship in ships_finished:
            self.current_vessels.remove(ship)

    def ship_destroyed(self, ship: Ship) -> None:
        self.current_vessels.remove(ship)

    def calculate_drone_movements(self) -> None:
        for drone in self.current_airborne_drones:
            drone.move()

    def time_step(self) -> None:
        print(f"Starting iteration {self.world_time: .3f}")
        self.world_time += self.time_delta

        self.update_weather_conditions()

        for uav in self.drones:
            if uav.under_maintenance:
                uav.check_if_complete_maintenance()

        for management in self.escort_management:
            management.manage_escorts()

        t_0 = time.perf_counter()
        self.create_arriving_merchants()
        self.calculate_ship_movements()
        t_1 = time.perf_counter()
        self.time_spent_on_merchants += (t_1 - t_0)

        t_0 = time.perf_counter()
        self.launch_drone()
        self.calculate_drone_movements()
        t_1 = time.perf_counter()
        self.time_spent_on_UAVs += (t_1 - t_0)

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


class Landmass:
    def __init__(self, name: str, polygon: Polygon, color="grey"):
        self.name = name
        self.polygon = polygon
        self.color = color

    def __str__(self):
        return f"Landmass {self.name}"

    def add_landmass_to_plot(self, axes):
        axes = self.polygon.add_polygon_to_plot(axes, color=self.color, opacity=0.8)
        return axes
