# ---- DEBUG PARAMETERS ----
axes_plot = None

ITERATION_LIMIT = 50
DEBUG_MODE = True
PLOTTING_MODE = True

RECEPTOR_PLOT_PARAMETER = "sea_states"  # ["sea_states", "pheromones"]

# ---- PERFORMANCE MEASURING ----
time_spent_creating_routes = 0
time_spent_calculating_distance = 0
time_spent_making_patrol_moves = 0
time_spent_observing_area = 0
time_spreading_pheromones = 0
time_spent_updating_trail_route = 0
time_spent_uav_route_move = 0
time_spent_checking_uav_return = 0
time_spent_depreciating_pheromones = 0
time_spent_following_route = 0
time_spent_launching_drones = 0

time_spent_selecting_receptors = 0

# ---- World Constants ----
world = None
WEATHER_RESAMPLING_TIME_SPLIT = 1

# ---- GEO Constants ----
EXPANSION_PARAMETER = 0.001  # Parameter to slightly extend polygons to prevent overlaps when selecting a point

LATITUDE_CONVERSION_FACTOR = 110.574
LONGITUDE_CONVERSION_FACTOR = 111.320
MIN_LAT = 110
MAX_LAT = 150

MIN_LONG = 5
MAX_LONG = 50

GRID_WIDTH = 1
GRID_HEIGHT = GRID_WIDTH

PLOT_SIZE = 7

LAT_GRID_EXTRA = 6
LONG_GRID_EXTRA = 6

# ----- World Rules ------

japan_route = False  # TODO: Force Merchant Route through Japanese territorial waters if True

# HUNTER RULES
# TODO: Implement
hunter_behaviour = "respect_exclusion"  # ["respect_exclusion", "cross_if_pursuit", "free_hunt"]
# respect_exclusion: Hunters stay out of exclusion zone all the time [default]
# cross_if_pursuit: Hunters cross exclusion zone if in pursuit of merchant and NO ESCORT is present
# free_hunt: Hunters hunt in exclusion zone (accepting casualties from escorts, aircraft, attack helicopters, or CDCMs)

# GENERAL ESCORT BEHAVIOUR PARAMETERS
taiwan_escort_behaviour = {"patrol": 0.5,
                           "hunt": 0,
                           "guard": 0.5
                           }
us_escort_behaviour = {"patrol": 1/3,
                       "hunt": 1/3,
                       "guard": 1/3
                       }
japan_escort_behaviour = {"patrol": 0.4,
                          "hunt": 0.2,
                          "guard": 0.4
                          }

# TAIWAN ESCORT RULES
# TODO: Implement
taiwan_engagement = "attack_all"  # ["engaged_only", "attack_all"] -
# engaged_only: only engages hunters in the act of boarding or attacking merchants, and all hunters in exclusion zone
# attack_all  : Attack all hunters

# JAPAN ENGAGEMENT RULES
# TODO: Implement
japan_engagement = "never_attack"  # ["never_attack",  "attack_territorial", "attack_contiguous_zone",
#                                     "attack_inner_ADIZ", "attack_outer_ADIZ", "attack_all"]

# ---- Pheromone ----
PHEROMONE_DEPRECIATION_FACTOR_PER_TIME_DELTA = 0.99
RECEPTOR_RADIUS_MULTIPLIER = 10

# ---- UAV Parameters ----
UAV_HEALTH = 100
MAX_TRAILING_DISTANCE = 0.01

SAFETY_ENDURANCE = 0.05

PATROL_MIN_LAT = 117
PATROL_MAX_LAT = 150

PATROL_MIN_LONG = 10
PATROL_MAX_LONG = 40

UAV_AVAILABILITY = 0.3

# ---- Detection Parameters ----
UAV_MOVEMENT_SPLITS_P_H = 24  # (24 is at least 2 every 5 mins) Splits per hour - gets recalculated per timedelta
PATROL_LOCATIONS = 10  # Number of locations to sample and compare

K_CONSTANT = 39_633

# ---- Vessel Constants ----

MERCHANT_HEALTH = 100
ESCORT_HEALTH = 100
SHIP_DOCKING_TIME = 1  # Time ship needs to enter docking area

CARGO_DAILY_ARRIVAL_MEAN = 30
BULK_DAILY_ARRIVAL_MEAN = 30
CONTAINER_DAILY_ARRIVAL_MEAN = 30

# Cargo Ships
CARGO_AVERAGE_SPEED = 80
CARGO_AVERAGE_LOAD = 1
CARGO_RCS = 1

# Bulk Ships
BULK_AVERAGE_SPEED = 60
BULK_AVERAGE_LOAD = 1
BULK_RCS = 1.25

# Container Ships
CONTAINER_AVERAGE_SPEED = 45
CONTAINER_AVERAGE_LOAD = 1
CONTAINER_RCS = 1.5

CRUISING_SPEED = 12 * 1.852

ESCORT_MAINTENANCE_TIME = 6  # Time for escorts to refuel/resupply
MERCHANT_MAINTENANCE_TIME = 3 * 24  # Time for merchants to return overseas

# ---- Plotting Constants -----
WORLD_MARKER_SIZE = 7
STANDARD_ROUTE_COLOR = "red"
ROUTE_OPACITY = 0.5
MERCHANT_COLOR = "black"
US_ESCORT_COLOR = "navy"
TAIWAN_ESCORT_COLOR = "forestgreen"
JAPAN_ESCORT_COLOR = "white"
UAV_COLOR = "indianred"
RECEPTOR_COLOR = "green"
