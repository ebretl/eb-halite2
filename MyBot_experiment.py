import hlt
import logging
import time
import random
import numpy as np
import itertools
import collections
import math

from matplotlib import pyplot as plt
plt.ion()

UNDOCKED = hlt.entity.Ship.DockingStatus.UNDOCKED

game = hlt.Game("im different")

while True:
    game_map = game.update_map()
    t_start = time.time()
    n_players = len(game_map.all_players())
    me = game_map.get_me()

    all_entities = game_map._all_ships() + game_map.all_planets()
    random.shuffle(all_entities)

    all_my_ships = list(game_map.get_me().all_ships())
    ship_radius = 0.7
    # for s in all_my_ships:
    #     s.radius = ship_radius

    live_ships = [x for x in game_map.get_me().all_ships() if x.docking_status==UNDOCKED]
    random.shuffle(live_ships)

    enemy_ships = []
    live_enemy_ships = []
    most_enemy_ships = 0
    for player in game_map.all_players():
        if player.id != me.id:
            their_ships = player.all_ships()
            enemy_ships += their_ships
            most_enemy_ships = max(most_enemy_ships, len(their_ships))
            for s in their_ships:
                if s.docking_status == s.DockingStatus.UNDOCKED:
                    live_enemy_ships.append(s)
    # if len(live_enemy_ships) == 0:
    #     live_enemy_ships.append(enemy_ships[0])

    planet_enemies = dict()
    planet_friendlies = dict()
    for p in game_map.all_planets():
        planet_enemies[p] = [s for s in live_enemy_ships
                if p.calculate_distance_between(s) < p.radius+40]
        planet_friendlies[p] = [s for s in live_ships
                if p.calculate_distance_between(s) < p.radius+40]

    def planet_safe(pl):
        return len(planet_enemies[pl]) == 0 \
            or len(planet_friendlies[pl]) >= 1.5 * len(planet_enemies[pl])

    def pos_dist(pos1, pos2):
        return ((pos1[0]-pos2[0])**2 + (pos1[1]-pos2[1])**2) ** 0.5

    def ent_dist(e1, e2):
        return e1.calculate_distance_between(e2)

    def is_ship(e):
        return type(e) == hlt.entity.Ship
    def is_planet(e):
        return type(e) == hlt.entity.Planet
    def is_mine(e):
        return e.owner and e.owner.id == me.id


    ent_values = collections.Counter()
    for ent in all_entities:
        if is_planet(ent):
            v = ent.num_docking_spots
            if planet_safe(ent) and not is_mine(ent):
                v *= 1.5
            if n_players == 4:
                cx = game_map.width / 2
                cy = game_map.height / 2
                v *= ((pos_dist((ent.x,ent.y),(cx,cy)) / 400) + 1)

        elif is_ship(ent):
            if ent.docking_status == UNDOCKED:
                v = 0.2 if is_mine(ent) else 1
            else: # docked
                v = 1 if is_mine(ent) else 5

        ent_values[ent] = v


    def max_val_target(pos):
        vs = [ent_values[e] / pos_dist(pos,(e.x,e.y))
                for e in all_entities if (e.x,e.y)!=pos]
        i = np.argmax(vs)
        return vs[i], all_entities[i]

    def pos_val(pos):
        vs = [ent_values[e] / pos_dist(pos,(e.x,e.y))
                for e in all_entities if (e.x,e.y) != pos]
        return sum(vs)

    # mapvis = []
    # for y in range(0, game_map.height, 4):
    #     mapvis.append([])
    #     for x in range(0, game_map.width, 4):
    #         mapvis[-1].append( pos_value((x,y)) )
    # plt.imshow(np.array(mapvis))
    # plt.show()
    # plt.pause(0.1)

    inbounds = lambda pos: pos[0]>ship_radius and pos[0]<game_map.width-ship_radius \
                       and pos[1]>ship_radius and pos[1]<game_map.height-ship_radius

    nav_targets = dict()

    def obstacles_between(pos1, pos2, ignore=tuple()):
        vel_x = pos2[0] - pos1[0]
        vel_y = pos2[1] - pos1[1]
        
        for obs in all_entities:
            if (obs.x, obs.y) in ignore:
                continue
            xdiff = pos1[0] - obs.x
            ydiff = pos1[1] - obs.y
            if obs in nav_targets:
                vxdiff = vel_x - nav_targets[obs][0] + obs.x
                vydiff = vel_y - nav_targets[obs][1] + obs.y
            else:
                vxdiff, vydiff = vel_x, vel_y
            if vxdiff != 0 or vydiff != 0: 
                t = -(xdiff*vxdiff + ydiff*vydiff) / (vxdiff**2 + vydiff**2)
            else:
                t = 0
            if t < 0: t = 0
            if t > 1: t = 1
            x = pos1[0] + vel_x * t
            y = pos1[1] + vel_y * t
            if obs in nav_targets:
                ox = obs.x + (nav_targets[obs][0] - obs.x) * t
                oy = obs.y + (nav_targets[obs][1] - obs.y) * t
            else:
                ox, oy = obs.x, obs.y
            if ((x-ox)**2+(y-oy)**2) <= (ship_radius+obs.radius)**2:
                # collided
                return True
        return False

    command_queue = []

    for ship in live_ships:
        if time.time() - t_start > 1.3:
            break

        thrusts = [2.0, 3.25, 4.5, 5.75, 7.0]
        angles = list(np.arange(0, 2*math.pi, math.pi/12))
        pos1 = (ship.x, ship.y)
        best_pos = pos1
        # best_val, _ = max_val_target(pos1)
        best_val = pos_val(pos1)
        for t,a in itertools.product(thrusts, angles):
            pos2 = ship.x+t*math.cos(a), ship.y+t*math.sin(a)
            if not obstacles_between(pos1, pos2, ignore=(pos1,)) \
                    and inbounds(pos2):
                # v, _ = max_val_target(pos2)
                v = pos_val(pos2)
                if v > best_val:
                    best_pos = pos2
                    best_val = v

        if best_pos != pos1:
            nav_targets[ship] = best_pos
            a = math.atan2(best_pos[1]-pos1[1], best_pos[0]-pos1[0])
            t = pos_dist(pos1, pos2)
            command_queue.append(ship.thrust(int(t), math.degrees(a)))
            assert not obstacles_between(pos1, best_pos, ignore=(pos1,))

    game.send_command_queue(command_queue)
