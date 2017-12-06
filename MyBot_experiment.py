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

game = hlt.Game("EB16")

while True:
    game_map = game.update_map()
    t_start = time.time()
    n_players = len(game_map.all_players())
    me = game_map.get_me()

    all_entities = game_map._all_ships() + game_map.all_planets()

    all_my_ships = list(game_map.get_me().all_ships())
    # ship_radius = 0.8
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


    def pos_value(pos):
        return sum((
            ent_values[e] / (pos_dist(pos,(e.x,e.y)) + 0.1)
            for e in all_entities
        ))

    # mapvis = []
    # for y in range(0, game_map.height, 4):
    #     mapvis.append([])
    #     for x in range(0, game_map.width, 4):
    #         mapvis[-1].append( pos_value((x,y)) )
    # plt.imshow(np.array(mapvis))
    # plt.show()
    # plt.pause(0.1)

    nav_targets = dict()

    def obstacles_between(pos1, pos2):
        for e in all_entities:
            

    command_queue = []
    for ship in live_ships:
        thrusts = [7,5,3,1]
        angles = np.arange(0, 2*math.pi, math.pi/12)
        pos1 = (ship.x, ship.y)
        best_pos = pos1
        best_sep = h(pos1)
        for t,a in itertools.product(thrusts, angles):
            pos2 = ship.x+t*math.cos(a), ship.y+t*math.sin(a)
            if not obstacles_between(pos1, pos2, ignore=pos1) \
                    and h(pos2) > best_sep \
                    and inbounds(pos2):
                best_pos = pos2
                best_sep = h(pos2)
