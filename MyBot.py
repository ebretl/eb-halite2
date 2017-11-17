import hlt
import logging
import time
import random
import numpy as np
import itertools
import math

game = hlt.Game("EB7")

while True:
    game_map = game.update_map()
    t_start = time.time()

    my_id = game_map.my_id
    n_players = len(game_map.all_players())
    command_queue = []

    all_my_ships = list(game_map.get_me().all_ships())
    ship_radius = 1.0
    for s in all_my_ships:
        s.radius = ship_radius

    live_ships = [x for x in game_map.get_me().all_ships() if x.docking_status == x.DockingStatus.UNDOCKED]
    checkpoint(1)

    get_owner_id = lambda pl: pl.owner.id if pl.owner else -1

    owned = [x for x in game_map.all_planets() if get_owner_id(x) == my_id]
    nonfull = [x for x in owned if not x.is_full()]
    if len(owned) == 0:
        owned += live_ships
    unowned = [x for x in game_map.all_planets() if get_owner_id(x) != my_id]
    if len(unowned) == 0:
        command_queue.append(game_map.get_me().all_ships()[0].thrust(0,0))
        game.send_command_queue(command_queue)
        continue
    checkpoint(2)

    enemy_ships = []
    for player in game_map.all_players():
        if player.id != my_id:
            enemy_ships += player.all_ships()
    checkpoint(3)

    def ship_danger(e):
        if n_players == 4:
            if len(enemy_ships) <= 10:
                sample = enemy_ships
            else:
                sample = random.sample(enemy_ships, 10)
            d = sum((e.x-s.x)**2 + (e.y-s.y)**2 for s in sample)
            if d == 0:
                return 1
            else:
                return d ** -0.5
        else: # n_players == 2
            return 1

    def ship_planet_cost(s, p):
        return (s.calculate_distance_between(p) 
                / p.num_docking_spots 
                * ship_danger(p)
                )
    
    def ship_ship_cost(s1, s2):
        return (s1.calculate_distance_between(s2) 
                / 1.5 
                * ship_danger(s2)
                )
    
    def best_ship(s):
        closest_ships = sorted(enemy_ships, key=lambda ss: s.calculate_distance_between(ss))[:5]
        return min(closest_ships, key=lambda ss: ship_ship_cost(s,ss))
    
    def nearest_planet(s):
        return min(unowned+nonfull, key=lambda p: s.calculate_distance_between(p))
    def best_planet(s):
        closest_planets = sorted(unowned+nonfull, key=lambda p: s.calculate_distance_between(p))[:5]
        return min(closest_planets, key=lambda p: ship_planet_cost(s,p))

    def best_entity(s):
        bs = best_ship(s)
        bp = best_planet(s)
        return bs if ship_ship_cost(s,bs) < ship_planet_cost(s,bp) else bp

    def can_dock(s, p):
        return s.can_dock(p) and (not p.is_full()) and (get_owner_id(p) in (-1, my_id))

    def get_target_around(x):
        if type(x) == hlt.entity.Planet:
            if get_owner_id(x) in (-1, my_id):
                return x
            else:
                return iter(x.all_docked_ships()).__next__()
        elif type(x) == hlt.entity.Ship:
            return x
        else:
            return None


    graph = dict()
    # openlist = [(e.x, e.y) for e in game_map._all_ships()+game_map.all_planets()]
    for i in range(1000):
        x = random.random() * game_map.width
        y = random.random() * game_map.height
        good = True
        for e in itertools.chain(game_map._all_ships(), game_map.all_planets()):
            if ((e.x-x)**2 + (e.y-y)**2)**0.5 <= ship_radius + e.radius:
                good = False
                break
        if good:
            near = min(graph.keys(), key=lambda x,y: )


    random.shuffle(live_ships)
    # for ship in sorted(live_ships, key=lambda s: s.calculate_distance_between(best_entity(s))):
    for i, ship in enumerate(sorted(live_ships, key=lambda s: s.calculate_distance_between(nearest_planet(s)))):
        if time.time() - t_start > 1.25:
            break

        checkpoint(i)
        
        if can_dock(ship, nearest_planet(ship)):
            command_queue.append(ship.dock(nearest_planet(ship)))
        else:
            cmd = ship.navigate(
                ship.closest_point_to(get_target_around(best_entity(ship))), 
                game_map, 
                speed=7, 
                ignore_ships=False,
                max_corrections=90
            )
            if cmd:
                command_queue.append(cmd)

    if len(command_queue) == 0:
        command_queue.append(game_map.get_me().all_ships()[0].thrust(0,0))
    
    game.send_command_queue(command_queue)

    # time.sleep(min(1.9-time.time()+t_start, 1.0))
