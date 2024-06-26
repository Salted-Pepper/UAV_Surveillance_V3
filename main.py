from world import World
import matplotlib

matplotlib.use("Agg")
from matplotlib.animation import FuncAnimation

test_world = World(time_delta=0.2)


def animation_function(frame):
    test_world.time_step()


anim_created = FuncAnimation(test_world.fig, animation_function, frames=5 * 72, interval=100, repeat=False)

anim_created.save("animated_arrivals.mp4", writer="ffmpeg")

print("Simulation Completed.")
