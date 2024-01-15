import constants
from points import Point


class Base:
    """
    A Harbour/Port/Dock OR an Oiler able to resupply and perform general maintenance
    """
    def __init__(self, name: str, location: Point):
        self.name = name
        self.location = location

        self.currently_served_agent = None
        self.stationed_agents = []
        self.maintenance_queue = []
        self.maintenance_prep_time = 0.1  # Time to switch maintenance from one unit to another.

        self.color = "black"

    def add_to_plot(self) -> None:
        self.location.add_point_to_plot(constants.axes_plot, color=self.color, marker="8", plot_text=False,
                                        marker_edge_width=2, markersize=constants.WORLD_MARKER_SIZE - 4)

    def agent_returns(self, agent: object) -> None:
        self.stationed_agents.append(agent)
        self.maintenance_queue.append(agent)

    def start_serve_next_agent(self):
        if len(self.maintenance_queue) > 0:
            self.currently_served_agent = self.maintenance_queue.pop(0)
        else:
            pass

    def finish_maintenance_agent(self):
        self.currently_served_agent.complete_maintenance()
        self.start_serve_next_agent()

    def serve_agent(self):
        remaining_time = constants.world.time_delta
        while remaining_time > 0:
            if self.currently_served_agent is not None:
                # Either complete ship maintenance
                if self.currently_served_agent.remaining_service_time < remaining_time:
                    remaining_time -= self.currently_served_agent.remaining_service_time
                    self.finish_maintenance_agent()
                # Continue part of the ship service
                else:
                    self.currently_served_agent.remaining_service_time -= remaining_time
                    return
            # No Ship is currently served, but queue existing
            elif self.currently_served_agent is None and len(self.maintenance_queue) > 0:
                self.start_serve_next_agent()
                remaining_time -= self.maintenance_prep_time
            # Nothing to serve
            else:
                return


class Airbase(Base):
    def __init__(self, name: str, location: Point):
        super().__init__(name, location)

    def __str__(self):
        return f"Airbase {self.name} at {self.location}"


class Harbour(Base):
    def __init__(self, name: str, location: Point):
        super().__init__(name, location)

