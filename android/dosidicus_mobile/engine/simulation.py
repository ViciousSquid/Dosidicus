"""Simulation - the tick loop that binds squid, brain and world together.

This is the mobile analogue of ``TamagotchiLogic``: it owns the food in the
tank, advances time, runs the brain (propagate -> Hebbian learn ->
neurogenesis), lets the squid decide and move, and handles save/load. It has no
UI dependency, so it can be driven by Kivy's Clock, a test, or a headless loop.
"""

from __future__ import annotations

import json
import math
import os
import random
import time

from .squid import Squid
from .personality import Personality
from .statistics import Statistics
from .achievements import AchievementManager


class Simulation:
    def __init__(self, tank_size=(900, 500), squid: Squid = None):
        self.tank_size = tank_size
        self.squid = squid or Squid(tank_size=tank_size)
        self.squid.tank_size = tank_size
        self.food_items = []          # list of {"x","y","type"}
        self.poop_items = []          # list of {"x","y"}
        # Decorations placed by the caretaker. Each: {id, type (asset file),
        # category (plant/rock/...), x, y (centre, tank coords), scale}.
        self.decorations = []
        self._food_id = 0
        self._decoration_id = 0
        self._poop_timer = 0.0
        self._decision_timer = 0.0
        self._decision_interval = 1.0  # squid re-decides roughly once a second
        self.last_status = self.squid.status
        self.newborn_neuron = None     # set for one tick when neurogenesis fires
        self._prev_can_see_food = False
        self._rock_velocities = {}     # deco_id -> [vx, vy] for thrown rocks
        self.sweep_x = None            # x of the cleaning sweep bar (None = idle)
        self.stats = Statistics()
        self._prev_pos = (self.squid.x, self.squid.y)
        self._was_sick = self.squid.is_sick
        self._near_plants = set()
        self.ink_clouds = []           # [{x, y, t (sim_time), ttl}]
        self._startle_cooldown = 0.0
        # Sleep consolidation: replay + memory promotion fire when the squid
        # falls asleep. Set for one tick after a consolidation so the UI can flash.
        self._was_sleeping = self.squid.is_sleeping
        self.sleep_consolidation = None
        # Starvation / game over: prolonged severe hunger is fatal.
        self.STARVE_HUNGER = 90.0      # hunger at/above this counts as starving
        self.STARVE_SECONDS = 300.0    # ...for this long (5 real-world minutes)
        self._starving_time = 0.0
        self.game_over = self.squid.is_dead
        # Achievements (mobile port of the desktop plugin). The app wires an
        # on_unlock callback for the toast; events fire from update()/care API.
        self.achievements = AchievementManager()
        self._ach_eval_timer = 0.0
        # Visiting squids received from nearby players (local peer-to-peer). Each
        # is a transient guest that wanders the tank and then leaves; not saved.
        self.visitors = []
        self._visitor_minds = {}
        self._visitor_id = 0
        self._watching = None      # the visitor whose arrival holds the gaze
        self.visitor_event = None   # set for one tick when a visitor does something
        # Territorial fight between the resident and a visitor (transient).
        self.fight = None
        self._fight_cooldown = 0.0
        # Egg hatching: a new game begins as an egg that plays its frames
        # (1/second) before the squid emerges.
        self.hatching = False
        self.hatch_t = 0.0
        self.hatch_frames = 6          # anim01..anim06, one per second

    # ------------------------------------------------------------- world API
    #: How far a squid perceives food.
    PERCEPTION_RADIUS = 260

    def food_visible(self):
        """Squid can see food within a perception radius."""
        return any(
            math.hypot(self.squid.x - f["x"], self.squid.y - f["y"]) <= self.PERCEPTION_RADIUS
            for f in self.food_items
        )

    def _squid_proximity(self, x, y, others):
        """How near the nearest of `others` is, 0-100, as on desktop."""
        from src.vision_cone import proximity
        w, h = self.tank_size
        inside = [(ox, oy) for ox, oy in others if 0 <= ox <= w and 0 <= oy <= h]
        if not inside:
            return 0.
        return proximity(min(math.hypot(ox - x, oy - y) for ox, oy in inside))

    def _sees_squid_at(self, x, y, facing, other_x, other_y):
        """Another squid, seen as the desktop squid sees one: by the view cone
        (src/vision_cone.py) pointed the way this squid faces, in the tank."""
        from src.vision_cone import FACING_ANGLES, VIEW_CONE_ANGLE, in_view_cone
        w, h = self.tank_size
        return (0 <= other_x <= w and 0 <= other_y <= h
                and in_view_cone(x, y, FACING_ANGLES.get(facing, 0.0), VIEW_CONE_ANGLE,
                                 math.hypot(w, h), other_x, other_y))

    def _notice_newcomers(self, squid):
        """A visitor coming into the tank catches the resident's eye, as on desktop.

        The resident turns to it as it enters and watches it while the gaze
        holds (Squid.notice); whether it is then seen is the view cone's call.
        """
        w, h = self.tank_size
        for v in self.visitors:
            if not v.get('noticed') and 0 <= v['x'] <= w and 0 <= v['y'] <= h:
                v['noticed'] = True
                if squid.notice(v['x']):
                    self._watching = v['id']
        if not squid.noticing:
            return
        watched = next((v for v in self.visitors if v['id'] == self._watching), None)
        if watched is None:
            squid.stop_noticing()     # it has gone; nothing to look at
        else:
            squid.look_towards(watched['x'])

    MAX_FOOD = 5  # never let the tank get more crowded than this

    def drop_food(self, x=None, y=None, food_type="sushi"):
        if len(self.food_items) >= self.MAX_FOOD:
            return None  # tank is full — ignore extra food
        w, h = self.tank_size
        self._food_id += 1
        item = {
            "x": x if x is not None else random.uniform(40, w - 40),
            "y": y if y is not None else 40,
            "type": food_type,
            "id": self._food_id,
        }
        self.food_items.append(item)
        return item

    # ------------------------------------------------------- decorations API
    def add_decoration(self, type, category, x, y, scale=1.0):
        """Place a decoration; a new object in the tank is a novel stimulus."""
        self._decoration_id += 1
        deco = {"id": self._decoration_id, "type": type, "category": category,
                "x": float(x), "y": float(y), "scale": float(scale)}
        self.decorations.append(deco)
        self.squid.brain.register_novelty(2.5)
        self.squid.curiosity = min(100.0, self.squid.curiosity + 5.0)
        self.squid.remember("decoration", category, f"New {category} appeared",
                            {"curiosity": 5}, importance=1.5)
        self.achievements.on_decoration_added()
        return deco

    def update_decoration(self, deco_id, x=None, y=None, scale=None):
        for d in self.decorations:
            if d["id"] == deco_id:
                if x is not None:
                    d["x"] = float(x)
                if y is not None:
                    d["y"] = float(y)
                if scale is not None:
                    d["scale"] = float(scale)
                return d
        return None

    def remove_decoration(self, deco_id):
        self.decorations = [d for d in self.decorations if d["id"] != deco_id]

    # --------------------------------------------------------- rock play
    def _rock_decorations(self):
        return [d for d in self.decorations if d.get("category") == "rock"]

    def _deco_by_id(self, deco_id):
        return next((d for d in self.decorations if d["id"] == deco_id), None)

    def _update_rock_play(self, dt):
        """The squid can approach a rock, pick it up, carry it, then throw it.

        Ported from the desktop rock interaction: pick up within ~45px when not
        sleeping, carry for a few seconds, then fling it — a rewarding form of
        play (extra reward for GREEDY squids)."""
        squid = self.squid
        now = squid.brain.sim_time

        # Fly any thrown rocks: gravity pulls them down to the sandy floor. A
        # rock thrown hard enough can leave the play area, and is then deleted.
        floor = self.tank_size[1] - 40
        w = self.tank_size[0]
        margin = 70
        for rid, vel in list(self._rock_velocities.items()):
            rock = self._deco_by_id(rid)
            if rock is None:
                self._rock_velocities.pop(rid, None)
                continue
            vel[1] += 520.0 * dt                       # gravity (y grows downward)
            rock["x"] += vel[0] * dt
            rock["y"] += vel[1] * dt
            vel[0] *= (1.0 - 0.4 * dt)                 # light drag on x
            if rock["x"] < -margin or rock["x"] > w + margin or rock["y"] < -margin:
                self.remove_decoration(rock["id"])     # left the tank -> gone
                self._rock_velocities.pop(rid, None)
                continue
            if rock["y"] >= floor:                     # landed
                rock["y"] = floor
                self._rock_velocities.pop(rid, None)
            elif (self._startle_cooldown <= 0 and not squid.is_fleeing
                  and math.hypot(squid.x - rock["x"], squid.y - rock["y"]) < 55):
                self.startle("rock")           # a rock whizzed past — fright!

        if squid.is_sleeping:
            return

        # Carrying: the rock rides just above the squid until it's thrown.
        if squid.carrying_rock:
            rock = self._deco_by_id(squid.carried_rock_id)
            if rock is None:
                squid.carrying_rock = False
                squid.carried_rock_id = None
                return
            rock["x"] = squid.x
            rock["y"] = squid.y - 26
            if now >= squid._carry_until:
                direction = random.choice([-1.0, 1.0])
                # Variable strength: gentle lobs stay in the tank, hard throws
                # can sail out of the play area (and get cleaned up).
                vx = direction * random.uniform(220.0, 560.0)
                vy = -random.uniform(120.0, 340.0)
                self._rock_velocities[rock["id"]] = [vx, vy]
                squid.carrying_rock = False
                squid.carried_rock_id = None
                squid.satisfaction = min(100.0, squid.satisfaction + 18.0)
                squid.happiness = min(100.0, squid.happiness + 15.0)
                squid.curiosity = min(100.0, squid.curiosity + 8.0)
                if squid.personality == Personality.GREEDY:
                    squid.satisfaction = min(100.0, squid.satisfaction + 6.0)
                squid.brain.learn_from_playing()
                squid.remember("play", "rock_throw", "Threw a rock",
                               {"satisfaction": 18, "happiness": 15},
                               importance=2.0, related=["satisfaction", "curiosity"])
                self.stats.on_rock_thrown()
                self.achievements.on_rock_throw()
                self.last_status = "playfully tossing a rock"
            return

        # Not carrying: if the squid wants to play and a settled rock is around,
        # go for it (ignore rocks still in flight so it doesn't re-grab its throw).
        carried = self._visitor_carried_rocks()
        rocks = [r for r in self._rock_decorations()
                 if r["id"] not in self._rock_velocities and r["id"] not in carried]
        if not (squid.wants_to_play and rocks):
            return
        target = min(rocks, key=lambda r: squid._dist(r["x"], r["y"]))
        dist = squid._dist(target["x"], target["y"])
        if dist < 45:
            squid.carrying_rock = True
            squid.carried_rock_id = target["id"]
            squid._carry_until = now + random.uniform(3.0, 7.0)
            self.achievements.on_rock_pickup()
            self.last_status = "picked up a rock!"
        elif dist < 320:
            squid.move_towards(target["x"], target["y"])
            self.last_status = "going for a rock"

    # --------------------------------------------------------- startle / ink
    def startle(self, source="ambient"):
        """Trigger a fright: flee, spike anxiety, ~25% release an ink cloud."""
        squid = self.squid
        squid.startle(source)
        self.stats.on_startle()
        self.achievements.on_startle()
        self._startle_cooldown = 8.0
        squid.remember("mental_state", "startled", "Startled!",
                       {"anxiety": 30, "happiness": -8}, importance=2.0,
                       related=["anxiety"])

    def _create_ink_cloud(self):
        squid = self.squid
        self.ink_clouds.append({"x": squid.x, "y": squid.y,
                                "t": squid.brain.sim_time, "ttl": 3.0})
        self.stats.on_ink_cloud()
        self.achievements.on_ink_cloud()
        squid.remember("behaviour", "ink_cloud", "Startled — released an ink cloud!",
                       None, importance=1.5)

    def _update_startle(self, dt):
        squid = self.squid
        now = squid.brain.sim_time
        if self._startle_cooldown > 0:
            self._startle_cooldown -= dt

        # End a flee once its timer runs out.
        if squid.is_startled and now >= squid._startle_until:
            squid.is_startled = False
        # Flight is selected from act_flee, never forced by the startle flag.

        # Ambient chance of a fright, more likely when anxious (desktop rule).
        if self._startle_cooldown <= 0 and not squid.is_sleeping and self.fight is None:
            rate = 0.02                       # per second base chance
            if squid.anxiety > 70:
                rate *= squid.anxiety / 50.0
            if random.random() < rate * dt:
                self.startle("ambient")

    def _update_ink(self, dt):
        now = self.squid.brain.sim_time
        self.ink_clouds = [c for c in self.ink_clouds if now - c["t"] < c["ttl"]]

    def on_shake(self):
        """The player physically shook the device: the squid is badly rattled."""
        squid = self.squid
        squid.anxiety = min(100.0, squid.anxiety + 30.0)
        squid.happiness = max(0.0, squid.happiness - 12.0)
        squid.satisfaction = max(0.0, squid.satisfaction - 8.0)
        squid.brain.register_stress(1.0)
        squid.remember("mental_state", "shaken", "The whole world shook!",
                       {"anxiety": 30, "happiness": -12}, importance=2.0,
                       related=["anxiety"])
        if self.fight is None and not self.game_over:
            self.startle("shake")   # bolt + flee (also spikes anxiety further)

    # --------------------------------------------------------- visitors (P2P)
    VISIT_SECONDS = 150.0    # how long a received guest lingers before leaving
    PREVIEW_SECONDS = 45.0   # a local preview visitor leaves promptly

    def add_visitor(self, snapshot, name="a friend", seconds=None):
        """Spawn a guest squid from a received snapshot (a squid or sim dict).

        The visitor runs its imported neural network against the host tank's
        sensory inputs. Its learned actions drive its body without modifying
        the resident squid's brain. Returns the visitor dict.
        """
        sq = snapshot.get("squid", snapshot) if isinstance(snapshot, dict) else {}
        tint = sq.get("color_tint")
        if not tint and sq.get("tint_color"):
            tint = [c / 255.0 for c in sq["tint_color"]]
        w, h = self.tank_size
        now = self.squid.brain.sim_time
        from_left = random.random() < 0.5
        self._visitor_id += 1
        v = {
            "id": self._visitor_id,
            "name": str(name)[:24],
            "personality": sq.get("personality", "adventurous"),
            "tint": tuple(tint) if tint else None,
            "x": -40.0 if from_left else w + 40.0,
            "y": random.uniform(h * 0.25, h * 0.6),
            "vx": 60.0 if from_left else -60.0,
            "vy": random.uniform(-20, 20),
            "dir": "right" if from_left else "left",
            "leave_at": now + (seconds if seconds is not None else self.VISIT_SECONDS),
            "leaving": False,
            "stole": 0,
            "ink_cd": 0.0,
            "wants_rock": random.random() < 0.6,   # half the guests are here to loot a rock
            "carried_rock": None,
            "fighting": False,
        }
        # Visitors keep their own imported neural network. Host world state
        # becomes sensory input; their learned motor neurons choose behaviour.
        self._visitor_minds[v['id']] = Squid.from_dict(sq, self.tank_size) if sq.get('brain') else Squid(Personality.from_value(v['personality']), self.tank_size)
        self.visitors.append(v)
        self.squid.brain.register_novelty(2.0)   # a newcomer is exciting
        self.squid.curiosity = min(100.0, self.squid.curiosity + 6.0)
        self.stats.on_encounter()
        return v

    def _update_visitors(self, dt):
        if not self.visitors:
            return
        now = self.squid.brain.sim_time
        w, h = self.tank_size
        floor, ceil = h - 40, 40
        gone = []
        for v in self.visitors:
            if v["fighting"]:
                continue    # a fight (see _update_fight) owns this visitor's motion

            if not v["leaving"] and now >= v["leave_at"]:
                v["leaving"] = True
                v["vx"] = 100.0 if v["x"] > w * 0.5 else -100.0
                if v["carried_rock"] is not None:
                    self.visitor_event = f"{v['name']} is making off with a rock!"
                elif v["stole"]:
                    self.visitor_event = f"{v['name']} is leaving with your food!"

            if v["leaving"]:
                v["x"] += v["vx"] * dt
                v["y"] += v["vy"] * 0.3 * dt
                self._carry_rock(v)
                if v["x"] < -60 or v["x"] > w + 60:
                    # off-screen: any rock it grabbed goes home with it
                    if v["carried_rock"] is not None:
                        self.remove_decoration(v["carried_rock"])
                    gone.append(v)
                v["dir"] = "right" if v["vx"] >= 0 else "left"
                continue

            v["ink_cd"] = max(0.0, v["ink_cd"] - dt)
            mind = self._visitor_minds[v['id']]
            mind._last_dt = dt
            mind.x, mind.y = v['x'], v['y']
            mind.update_needs(dt)
            mind.plant_targets = [d for d in self.decorations if d.get('category') == 'plant']
            signals = mind.sync_stats_to_brain(bool(self.food_items))
            # The resident, as percepts - not neurons. The shared engine grows
            # the visitor's social senses from them.
            seen = self._sees_squid_at(v['x'], v['y'], v.get('dir', 'right'),
                                       self.squid.x, self.squid.y)
            mind.brain.perceive('squid_in_view', 100. if seen else 0.)
            mind.brain.perceive('squid_proximity', self._squid_proximity(
                v['x'], v['y'], [(self.squid.x, self.squid.y)]))
            mind.brain.perceive('in_fight', 100. if v['fighting'] else 0.)
            mind.brain.advance(dt, signals, mind.is_sleeping)
            if getattr(mind, '_visit_decision_at', -1) < mind.brain.sim_time:
                mind.decide(mind.brain.state, self.food_items)
                mind._visit_decision_at = mind.brain.sim_time
            action = mind.last_decision.get('chosen', 'idle')
            v['wants_rock'] = action == 'playing'

            # The chosen action drives the visitor's body, not loot priorities.
            # Priority 1: loot a rock (and carry it), if this guest wants one.
            rock = None
            if v["carried_rock"] is None and v["wants_rock"]:
                rock = min((r for r in self._rock_decorations()
                            if r["id"] not in self._rock_velocities
                            and r["id"] not in self._visitor_carried_rocks(exclude=v)),
                           key=lambda r: (r["x"] - v["x"]) ** 2 + (r["y"] - v["y"]) ** 2,
                           default=None)
            if v["carried_rock"] is not None:
                self._carry_rock(v)
                self._wander(v, dt)                       # roam while holding it
            elif rock is not None:
                if self._steer(v, rock["x"], rock["y"], dt) < 44:
                    v["carried_rock"] = rock["id"]
                    self.visitor_event = f"{v['name']} grabbed one of your rocks!"
                    self.squid.anxiety = min(100.0, self.squid.anxiety + 4.0)
            else:
                # Priority 2: steal food; else wander.
                target = min(self.food_items,
                             key=lambda f: (f["x"] - v["x"]) ** 2 + (f["y"] - v["y"]) ** 2,
                             default=None) if action == 'eating' else None
                if target is not None:
                    if self._steer(v, target["x"], target["y"], dt) < 42:
                        self.food_items.remove(target)
                        v["stole"] += 1
                        self.visitor_event = f"{v['name']} snatched your {target.get('type', 'food')}!"
                        s = self.squid
                        s.anxiety = min(100.0, s.anxiety + 6.0)
                        s.remember("mental_state", "food_stolen",
                                   f"{v['name']} stole my food!", {"anxiety": 6},
                                   importance=1.5, related=["anxiety"])
                        if random.random() < 0.2:
                            self.startle("visitor")
                elif action == 'approaching_plant' and mind.plant_targets:
                    plant = min(mind.plant_targets, key=lambda p: (p['x']-v['x'])**2 + (p['y']-v['y'])**2)
                    self._steer(v, plant['x'], plant['y'], dt)
                elif action in ('exploring', 'playing', 'fleeing'):
                    self._wander(v, dt)

            self._clamp_visitor(v, w, h, ceil, floor)
            self._carry_rock(v)     # keep a held rock glued to the visitor

            from src.brain_constants import ACTION_THRESHOLDS
            if (v["ink_cd"] <= 0 and mind.brain.state.get('act_ink', 0) >= ACTION_THRESHOLDS['act_ink']
                    and random.random() < .35):
                self.ink_clouds.append({"x": v["x"], "y": v["y"], "t": now, "ttl": 3.0})
                v["ink_cd"] = 12.0
                self.visitor_event = f"{v['name']} puffed an ink cloud!"
                self.squid.curiosity = min(100.0, self.squid.curiosity + 3.0)

            v["dir"] = "right" if v["vx"] >= 0 else "left"

        for v in gone:
            self.visitors.remove(v)
            self._visitor_minds.pop(v['id'], None)

    # ---- visitor movement helpers -------------------------------------
    def _steer(self, v, tx, ty, dt):
        """Blend the visitor's velocity toward a target; return the distance."""
        dx, dy = tx - v["x"], ty - v["y"]
        dist = math.hypot(dx, dy) or 1.0
        k = min(1.0, 2.5 * dt)
        v["vx"] += (dx / dist * 95 - v["vx"]) * k
        v["vy"] += (dy / dist * 95 - v["vy"]) * k
        v["x"] += v["vx"] * dt
        v["y"] += v["vy"] * dt
        return dist

    def _wander(self, v, dt):
        v["vx"] += random.uniform(-30, 30) * dt
        v["vy"] += random.uniform(-30, 30) * dt
        v["x"] += v["vx"] * dt
        v["y"] += v["vy"] * dt

    def _clamp_visitor(self, v, w, h, ceil, floor):
        v["vx"] = max(-95, min(95, v["vx"]))
        v["vy"] = max(-55, min(55, v["vy"]))
        if v["x"] < 30:
            v["x"], v["vx"] = 30, abs(v["vx"])
        elif v["x"] > w - 30:
            v["x"], v["vx"] = w - 30, -abs(v["vx"])
        if v["y"] < ceil:
            v["y"], v["vy"] = ceil, abs(v["vy"])
        elif v["y"] > floor:
            v["y"], v["vy"] = floor, -abs(v["vy"])

    def _carry_rock(self, v):
        """Keep a visitor's stolen rock riding just above it."""
        if v["carried_rock"] is None:
            return
        rock = self._deco_by_id(v["carried_rock"])
        if rock is None:
            v["carried_rock"] = None
        else:
            rock["x"], rock["y"] = v["x"], v["y"] - 24

    def _visitor_carried_rocks(self, exclude=None):
        return {v["carried_rock"] for v in self.visitors
                if v is not exclude and v["carried_rock"] is not None}

    def _visitor_by_id(self, vid):
        return next((v for v in self.visitors if v["id"] == vid), None)

    # ------------------------------------------------------------- fighting
    # Rough combat "strength" bias by personality (bold/aggressive win more).
    _FIGHT_BONUS = {
        Personality.STUBBORN: 0.35, Personality.ENERGETIC: 0.25,
        Personality.GREEDY: 0.2, Personality.ADVENTUROUS: 0.15,
        Personality.LAZY: -0.15, Personality.TIMID: -0.3,
    }

    def _update_fight(self, dt):
        """Territorial scrap between the resident and a nearby visitor.

        Sequence: the two swim together, both turn red and puff ink, "Aggression!
        FIGHTING!" shows, moods sour — then after a moment a winner is decided.
        """
        squid = self.squid
        now = squid.brain.sim_time
        if self._fight_cooldown > 0:
            self._fight_cooldown -= dt

        if self.fight is None:
            if (self._fight_cooldown > 0 or squid.is_sleeping or squid.is_fleeing
                    or self.game_over):
                return
            res_timid = squid.personality == Personality.TIMID
            for v in self.visitors:
                if v["leaving"] or v["fighting"]:
                    continue
                vis_timid = Personality.from_value(
                    v.get("personality", "adventurous")) == Personality.TIMID
                # A fight always has a (non-timid) instigator; two timid squids
                # never fight.
                bold = [who for who, timid in
                        (("resident", res_timid), ("visitor", vis_timid)) if not timid]
                if not bold:
                    continue
                if (math.hypot(squid.x - v["x"], squid.y - v["y"]) < 130
                        and random.random() < 0.7 * dt):
                    self._start_fight(v, instigator=random.choice(bold))
                    break
            return

        f = self.fight
        v = self._visitor_by_id(f["visitor_id"])
        if v is None:                      # opponent vanished
            self._end_fight(None)
            return

        if f['phase'] == 'approaching':
            distance = math.hypot(squid.x-v['x'], squid.y-v['y'])
            if distance > 38:
                step = min(distance/2, 100 * dt)
                dx, dy = (v['x']-squid.x)/distance*step, (v['y']-squid.y)/distance*step
                squid.x += dx; squid.y += dy
                v['x'] -= dx; v['y'] -= dy
                return
            f['phase'] = 'fighting'
            f['until'] = now + 3.5

        # Grapple: jitter around the midpoint between the two combatants.
        mx, my = (squid.x + v["x"]) / 2, (squid.y + v["y"]) / 2
        squid.x += (mx - squid.x) * min(1.0, 3 * dt) + random.uniform(-9, 9)
        squid.y += (my - squid.y) * min(1.0, 3 * dt) + random.uniform(-9, 9)
        v["x"] += (mx - v["x"]) * min(1.0, 3 * dt) + random.uniform(-9, 9)
        v["y"] += (my - v["y"]) * min(1.0, 3 * dt) + random.uniform(-9, 9)
        w, h = self.tank_size
        squid.x = max(30, min(w - 30, squid.x))
        squid.y = max(40, min(h - 40, squid.y))
        v["x"] = max(30, min(w - 30, v["x"]))
        v["y"] = max(40, min(h - 40, v["y"]))

        if f["phase"] == "fighting":
            squid.anxiety = min(100.0, squid.anxiety + 6.0 * dt)
            squid.happiness = max(0.0, squid.happiness - 3.0 * dt)
            if now >= f["until"]:
                self._resolve_fight(f, v)
        elif f["phase"] == "result" and now >= f["until"]:
            self._end_fight(v)

    def _start_fight(self, v, instigator="visitor"):
        if self.fight is not None:
            return
        squid = self.squid
        from src.personality import can_initiate_fight
        initiator = v.get('personality') if instigator == 'visitor' else squid.personality
        if not can_initiate_fight(initiator):
            return
        now = squid.brain.sim_time
        self.fight = {"visitor_id": v["id"], "phase": "approaching", "until": now + 3.5,
                      "instigator": instigator}
        squid.fighting = True
        v["fighting"] = True
        squid.is_fleeing = squid.is_startled = False
        squid.status = "fighting!"
        squid.happiness = max(0.0, squid.happiness - 12.0)
        squid.satisfaction = max(0.0, squid.satisfaction - 10.0)
        squid.anxiety = min(100.0, squid.anxiety + 20.0)
        if instigator == "resident":
            self.stats.on_fight_instigated()
        # The renderer draws one shared fight cloud after the approach.
        who = "Your squid" if instigator == "resident" else v["name"]
        squid.remember("mental_state", "fight",
                       f"{who} started a fight!", {"anxiety": 20, "happiness": -12},
                       importance=2.5, related=["anxiety"])
        self.visitor_event = "Aggression! FIGHTING!"

    def _resolve_fight(self, f, v):
        squid = self.squid
        res = random.random() + self._FIGHT_BONUS.get(squid.personality, 0.0)
        vis = random.random() + self._FIGHT_BONUS.get(
            Personality.from_value(v.get("personality", "adventurous")), 0.0)
        won = res >= vis
        f["phase"] = "result"
        f["until"] = squid.brain.sim_time + 2.0
        self.achievements.on_fight()
        if won:
            self.stats.on_fight_won()
            squid.satisfaction = min(100.0, squid.satisfaction + 15.0)
            squid.happiness = min(100.0, squid.happiness + 8.0)
            self.visitor_event = f"Your squid won the fight against {v['name']}!"
        else:
            self.stats.on_fight_lost()
            squid.anxiety = min(100.0, squid.anxiety + 15.0)
            squid.happiness = max(0.0, squid.happiness - 8.0)
            self.visitor_event = f"{v['name']} won the fight!"

    def _end_fight(self, v):
        self.squid.fighting = False
        if v is not None:
            v["fighting"] = False
            v["leaving"] = True        # the visitor heads home after the scrap
            v["vx"] = 110.0 if v["x"] > self.tank_size[0] * 0.5 else -110.0
        self.fight = None
        self._fight_cooldown = 25.0

    def _decoration_effects(self, dt):
        """Being near decorations shapes mood: plants soothe, rocks intrigue."""
        s = self.squid
        near_now = set()
        for d in self.decorations:
            if math.hypot(s.x - d["x"], s.y - d["y"]) < 120 * d.get("scale", 1.0):
                cat = d["category"]
                if cat == "plant":
                    s.anxiety = max(0.0, s.anxiety - 3.0 * dt)
                    s.satisfaction = min(100.0, s.satisfaction + 1.5 * dt)
                    near_now.add(d["id"])
                    if d["id"] not in self._near_plants:
                        self.stats.on_plant_interaction()
                        self.achievements.on_plant_interaction()
                elif cat == "rock":
                    s.curiosity = min(100.0, s.curiosity + 2.5 * dt)
        self._near_plants = near_now

    def _settle_food(self, dt):
        floor = self.tank_size[1] - 40
        for f in self.food_items:
            if f["y"] < floor:
                f["y"] = min(floor, f["y"] + 120 * dt)

    def _settle_poop(self, dt):
        # Poop sinks to the sandy floor, just like uneaten food.
        floor = self.tank_size[1] - 34
        for p in self.poop_items:
            if p["y"] < floor:
                p["y"] = min(floor, p["y"] + 90 * dt)

    def _try_eat(self):
        eaten = []
        from src.brain_constants import ACTION_THRESHOLDS
        driven_to_eat = self.squid._bound_action == 'eating' and self.squid.brain.sim_time < self.squid._bound_until
        if self.squid.is_sleeping or (not driven_to_eat and self.squid.brain.state.get('act_eat', 0) < ACTION_THRESHOLDS['act_eat']):
            return False
        for f in self.food_items:
            if math.hypot(self.squid.x - f["x"], self.squid.y - f["y"]) < 45:
                self.squid.feed(f["type"])
                self.stats.on_eat(f["type"])
                self.achievements.on_feed()
                eaten.append(f)
        for f in eaten:
            self.food_items.remove(f)
        return bool(eaten)

    def _process_neural_outputs(self):
        from src.brain_constants import ACTION_NEURONS, innate_bindings
        defaults = {n: hook for n, hook, *_ in innate_bindings()}
        brain = self.squid.brain
        for binding in brain._bindings:
            activation = brain.state.get(binding.neuron_name, 0.0)
            if binding.should_fire(activation, brain.sim_time):
                binding.last_fire_time = brain.sim_time
                binding.last_activation = activation
                if random.random() <= binding.probability:
                    # Ordinary innate movement competes via select_action;
                    # parallel reflexes and custom actuators fire here.
                    if (binding.neuron_name not in ACTION_NEURONS or binding.neuron_name in ('act_ink', 'act_collapse')
                            or binding.output_hook != defaults.get(binding.neuron_name)):
                        self._fire_output(binding.output_hook, activation, binding.hook_params)
            elif not binding.is_edge_pending(activation):
                binding.last_activation = activation

    def _fire_output(self, hook, activation, params):
        squid = self.squid
        behaviours = {
            'neuron_output_seek_food': 'eating', 'neuron_output_eat': 'eating',
            'neuron_output_flee': 'fleeing', 'neuron_output_approach_rock': 'playing',
            'neuron_output_seek_plant': 'approaching_plant', 'neuron_output_sleep': 'sleeping',
            'neuron_output_wander': 'exploring', 'neuron_output_explore': 'exploring',
        }
        if hook in behaviours:
            action = behaviours[hook]
            squid.wants_to_play = action == 'playing'
            squid._movement_action = action
            squid._bound_action = action
            squid._bound_until = squid.brain.sim_time + float(params.get('duration', 3.0))
            squid.brain.causal_learning.on_action(action, squid.brain.state)
            self.last_status = squid._execute(action, self.food_items)
        elif hook == 'neuron_output_ink_cloud':
            self._create_ink_cloud()
        elif hook == 'neuron_output_wake':
            squid.is_sleeping = False
        elif hook == 'neuron_output_startle':
            self.startle('neural output')
        elif hook in ('neuron_output_boost_happiness', 'neuron_output_boost_curiosity',
                      'neuron_output_reduce_anxiety'):
            stat = {'neuron_output_boost_happiness': 'happiness',
                    'neuron_output_boost_curiosity': 'curiosity',
                    'neuron_output_reduce_anxiety': 'anxiety'}[hook]
            delta = activation / 100.0 * 5.0 * (-1 if stat == 'anxiety' else 1)
            setattr(squid, stat, min(100.0, max(0.0, getattr(squid, stat) + delta)))
        elif hook == 'neuron_output_calm':
            squid.anxiety = max(0.0, squid.anxiety - 10.0)
            squid.is_fleeing = squid.is_startled = False
            squid._bound_action = None
            squid._bound_until = squid.brain.sim_time
            squid._movement_action = 'exploring'
        elif hook == 'neuron_output_change_color':
            channels = [params.get(channel, -1) for channel in ('red', 'green', 'blue')]
            if not all(isinstance(value, (int, float)) and value >= 0 for value in channels):
                channels = random.choice([(255, 100, 100), (100, 255, 100), (100, 100, 255),
                                          (255, 255, 100), (255, 100, 255), (100, 255, 255)])
            squid.color_tint = tuple(min(255, value) / 255.0 for value in channels)
        elif hook == 'neuron_output_throw_rock':
            if squid.carrying_rock:
                squid._carry_until = squid.brain.sim_time
                self._update_rock_play(0)
        elif hook == 'neuron_output_pick_up_rock':
            carried = self._visitor_carried_rocks()
            nearby = any(squid._dist(rock['x'], rock['y']) < 45
                         and rock['id'] not in self._rock_velocities
                         and rock['id'] not in carried for rock in self._rock_decorations())
            if nearby and not squid.is_sleeping and not squid.carrying_rock:
                squid.wants_to_play = True
                self._update_rock_play(0)

    # ---------------------------------------------------------------- update
    def start_hatching(self):
        self.hatching = True
        self.hatch_t = 0.0
        self.last_status = "an egg... something stirs inside"

    def update(self, dt: float):
        """Advance the whole simulation by ``dt`` seconds."""
        self.newborn_neuron = None
        self.sleep_consolidation = None
        self.visitor_event = None
        self.squid._last_dt = dt
        squid = self.squid

        # Game over: the squid has died. Freeze the world.
        if self.game_over:
            return self.last_status

        # While hatching, freeze the squid and just advance the egg animation
        # (one frame per second) until all frames have played.
        if self.hatching:
            self.hatch_t += dt
            if self.hatch_t >= self.hatch_frames:
                self.hatching = False
                self.last_status = "your squid has hatched!"
            return self.last_status

        # 1) Needs drift.
        squid.update_needs(dt)

        # Starvation: severe hunger sustained too long is fatal (game over).
        if squid.hunger >= self.STARVE_HUNGER:
            self._starving_time += dt
        else:
            self._starving_time = 0.0
        if self._starving_time >= self.STARVE_SECONDS:
            self.game_over = True
            squid.is_dead = True
            squid.is_sleeping = False
            squid.status = "starved"
            self.last_status = "Your squid has died of hunger."
            return self.last_status

        # Perception drives the same fixed-rate neural pipeline as desktop.
        can_see = self.food_visible()
        if can_see and not self._prev_can_see_food:
            squid.brain.register_novelty(2.0)
        self._prev_can_see_food = can_see
        if squid.is_sick and not self._was_sick:
            self.stats.on_sickness()
            squid.brain._reflexes.learn_from_sickness()
        self._was_sick = squid.is_sick
        squid.plant_targets = [d for d in self.decorations if d.get('category') == 'plant']
        clamped = squid.sync_stats_to_brain(can_see_food=can_see)
        self._notice_newcomers(squid)
        # Another squid, as on desktop, is percepts, not sense organs: the
        # shared engine grows its social senses from them the first time they
        # matter. Off-screen arrivals are not perceived.
        other_visible = any(self._sees_squid_at(squid.x, squid.y, squid.direction,
                                                v['x'], v['y'])
                            for v in self.visitors)
        squid.brain.perceive('squid_in_view', 100. if other_visible else 0.)
        squid.brain.perceive('squid_proximity', self._squid_proximity(
            squid.x, squid.y, [(v['x'], v['y']) for v in self.visitors]))
        squid.brain.perceive('in_fight', 100. if self.fight is not None else 0.)
        from types import SimpleNamespace
        squid.memory_manager = squid.memory
        self.brain_window = SimpleNamespace(brain_widget=squid.brain)
        squid.brain.tamagotchi_logic = self
        births = squid.brain.advance(dt, clamped, sleeping=squid.is_sleeping)
        for stat, delta in squid.brain.last_modulation.items():
            setattr(squid, stat, max(0.0, min(100.0, getattr(squid, stat) + delta)))
            squid.brain.state[stat] = getattr(squid, stat)
        for born in births:
            self.newborn_neuron = born
            fn = squid.brain.enhanced_neurogenesis.functional_neurons.get(born)
            kind = fn.neuron_type if fn else 'novelty'
            squid.remember("neurogenesis", born, f"Grew a {kind} neuron", None, importance=3.0)
            self.stats.on_neuron_born(kind)
            self.achievements.on_neuron_born()
        squid.brain.enhanced_neurogenesis.set_achievement_callbacks(
            on_leveled=lambda name, strength: self.achievements.on_neuron_levelled(strength))
        squid.memory.periodic(squid.brain.sim_time)
        self._process_neural_outputs()
        self._decision_timer += dt
        if self.fight is not None:
            self.last_status = "Aggression! FIGHTING!"   # a fight overrides normal behaviour
        elif self._decision_timer >= self._decision_interval:
            self._decision_timer = 0.0
            self.last_status = squid.decide(squid.brain.state, self.food_items)
        else:
            # Cognitive decisions are 1 Hz; the body follows the selected
            # neural drive every render frame, as on desktop.
            if not squid.is_sleeping:
                self.last_status = squid._execute(squid._movement_action, self.food_items)

        # Falling asleep triggers consolidation: replay the strongest recent
        # co-activations to cement them, and promote meaningful memories to
        # long-term storage (the mobile analogue of the desktop sleep replay).
        if squid.is_sleeping and not self._was_sleeping:
            replay = squid.brain.last_consolidation or {}
            promoted = squid.memory.consolidate_sleep(squid.brain.sim_time)
            self.sleep_consolidation = dict(replay, promoted=promoted)
            self.last_status = "drifting to sleep — consolidating memories"
            self.achievements.on_sleep_consolidated()
        elif self._was_sleeping and not squid.is_sleeping:
            self.achievements.on_wake()      # woke from a sleep
        self._was_sleeping = squid.is_sleeping

        # Achievement stat/age/time evaluation, ~once a second.
        self._ach_eval_timer += dt
        if self._ach_eval_timer >= 1.0:
            self._ach_eval_timer = 0.0
            self.achievements.evaluate(squid, self.stats)

        # 5) World interactions.
        self._update_startle(dt)
        self._update_ink(dt)
        self._update_visitors(dt)
        self._update_fight(dt)
        self._update_rock_play(dt)
        self._update_sweep(dt)
        self._decoration_effects(dt)
        self._settle_food(dt)
        self._settle_poop(dt)
        if self._try_eat():
            squid.is_eating = True
        else:
            squid.is_eating = False

        # Occasional poop when well-fed, which lowers cleanliness.
        self._poop_timer += dt
        if self._poop_timer > 20 and squid.hunger < 40 and random.random() < 0.05:
            self._poop_timer = 0.0
            self.poop_items.append({"x": squid.x, "y": squid.y + 20})
            squid.cleanliness = max(0.0, squid.cleanliness - 8.0)
            self.stats.on_poop(len(self.poop_items))

        # Lifetime statistics: distance moved this tick + per-tick accumulation.
        moved = math.hypot(squid.x - self._prev_pos[0], squid.y - self._prev_pos[1])
        self._prev_pos = (squid.x, squid.y)
        self.stats.tick(dt, squid, squid.brain, moved)

        return self.last_status

    def clean_tank(self):
        # Start a right-to-left sweep that removes food and poop as it passes
        # (mirrors the desktop cleaning line). The stat boost applies now.
        if self.sweep_x is None:
            self.sweep_x = float(self.tank_size[0])
        self.achievements.on_clean()
        return self.squid.clean()

    def _update_sweep(self, dt):
        if self.sweep_x is None:
            return
        self.sweep_x -= (self.tank_size[0] / 1.2) * dt   # ~1.2s to cross the tank
        x = self.sweep_x
        # Everything the bar has passed (to its right) is swept away.
        self.food_items = [f for f in self.food_items if f["x"] < x]
        self.poop_items = [p for p in self.poop_items if p["x"] < x]
        if self.sweep_x <= 0:
            self.sweep_x = None
            self.food_items = []
            self.poop_items = []

    # ---------------------------------------------------------- persistence
    def to_dict(self) -> dict:
        return {
            "version": 1,
            "desktop_sections": getattr(self, "_desktop_sections", {}),
            "saved_at": time.time(),
            "tank_size": list(self.tank_size),
            "squid": self.squid.to_dict(),
            "food_items": self.food_items,
            "poop_items": self.poop_items,
            "decorations": self.decorations,
            "statistics": self.stats.to_dict(),
            "achievements": self.achievements.to_dict(),
            "game_over": self.game_over,
            "starving_time": self._starving_time,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Simulation":
        tank = tuple(data.get("tank_size", (900, 500)))
        squid = Squid.from_dict(data["squid"], tank)
        sim = cls(tank, squid)
        sim._desktop_sections = data.get("desktop_sections", {})
        sim.food_items = data.get("food_items", [])
        sim.poop_items = data.get("poop_items", [])
        sim.decorations = data.get("decorations", [])
        sim._decoration_id = max([d["id"] for d in sim.decorations], default=0)
        sim.stats = Statistics.from_dict(data.get("statistics"))
        sim.achievements = AchievementManager.from_dict(data.get("achievements"))
        sim._prev_pos = (sim.squid.x, sim.squid.y)
        sim._was_sick = sim.squid.is_sick
        sim._was_sleeping = sim.squid.is_sleeping
        sim._starving_time = data.get("starving_time", 0.0)
        sim.game_over = data.get("game_over", sim.squid.is_dead)
        return sim

    def save(self, path: str):
        from .portability import export_squid
        export_squid(self, path)

    @classmethod
    def load(cls, path: str) -> "Simulation":
        import zipfile
        if zipfile.is_zipfile(path):
            from .portability import import_squid
            return import_squid(path)
        # Read old Android JSON saves once; future saves use the desktop ZIP.
        with open(path) as stream:
            return cls.from_dict(json.load(stream))
