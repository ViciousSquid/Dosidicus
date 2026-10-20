# File: vision_cone.py
"""The geometry of a squid's view cone, shared by everything that sees.

src/vision_worker.py runs the squid's vision with it; the multiplayer host
asks it of a visiting squid whose body it runs; the mobile game asks it of its
squid. One definition, and no Qt, so the mobile engine can share it.
"""

import math

#: A squid sees 72 degrees ahead (Squid.view_cone_angle).
VIEW_CONE_ANGLE = math.pi / 2.5

#: How far off another squid can be felt as near: across this range proximity
#: falls from 100 (touching) to 0. Closeness is felt whichever way the squid is
#: looking - the cone is for seeing, not for this.
PROXIMITY_RANGE = 400.0

#: Which way the cone points, for each way a squid can face.
FACING_ANGLES = {'right': 0.0, 'down': math.pi / 2, 'left': math.pi,
                 'up': -math.pi / 2}


def in_view_cone(viewer_x: float, viewer_y: float, view_angle: float,
                 cone_angle: float, cone_length: float,
                 target_x: float, target_y: float) -> bool:
    """Is the point (target_x, target_y) inside a squid's view cone?

    Centre to centre: the viewer's centre, pointing along view_angle, sees
    what lies within cone_angle of that direction and cone_length of it.
    """
    dx, dy = target_x - viewer_x, target_y - viewer_y
    if math.hypot(dx, dy) > cone_length:
        return False
    angle_diff = abs(math.atan2(dy, dx) - view_angle)
    while angle_diff > math.pi:
        angle_diff = 2 * math.pi - angle_diff
    return angle_diff <= cone_angle / 2


def proximity(distance: float) -> float:
    """How near another squid is, 0-100, from the distance between centres."""
    return max(0.0, min(100.0, 100.0 - float(distance) / PROXIMITY_RANGE * 100.0))


__all__ = ['VIEW_CONE_ANGLE', 'FACING_ANGLES', 'PROXIMITY_RANGE', 'in_view_cone',
           'proximity']
