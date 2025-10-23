from src.visualization import Visualization


def render_thread(*args, **kwargs):
    visualization = Visualization(*args, **kwargs)
    visualization.init_map()
    visualization.loop()
