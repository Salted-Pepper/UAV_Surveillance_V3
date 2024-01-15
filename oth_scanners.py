from points import Point


class OTH:
    def __init__(self, world, location: Point):

        self.world = world
        self.location = location

        # Scanning parameters
        self.range_band = 30
        self.scan_time = 1/60  # Scan one bandwidth per minute

        self.min_band = 700
        self.max_band = 3500

        self.enabled = True

    def detected_vessel(self):
        pass

    def roll_if_active(self):
        """

        :return:
        """
        pass
