import hlt
import logging
import time
import random
import numpy as np
import itertools
import math

game = hlt.Game("EB6")

LOG = False

while True:
    game_map = game.update_map()
    t_start = time.time()

    def checkpoint(ii):
        if LOG:
            logging.info("%d - %f" % (ii, time.time() - t_start))

    my_id = game_map.my_id
    n_players = len(game_map.all_players())
    command_queue = []

    all_my_ships = set(game_map.get_me().all_ships())
    for s in all_my_ships:
        s.radius = 1.01

    live_ships = [x for x in game_map.get_me().all_ships() if x.docking_status == x.DockingStatus.UNDOCKED]
    random.shuffle(live_ships)

    enemy_ships = []
    live_enemy_ships = []
    most_enemy_ships = 0
    for player in game_map.all_players():
        if player.id != my_id:
            their_ships = player.all_ships()
            enemy_ships += their_ships
            most_enemy_ships = max(most_enemy_ships, len(their_ships))
            for s in their_ships:
                if s.docking_status == s.DockingStatus.UNDOCKED:
                    live_enemy_ships.append(s)
    if len(live_enemy_ships) == 0:
        live_enemy_ships.append(enemy_ships[0])

    ship_ratio = len(all_my_ships) / most_enemy_ships

    get_owner_id = lambda pl: pl.owner.id if pl.owner else -1

    owned = set(x for x in game_map.all_planets() if get_owner_id(x) == my_id)
    nonfull = set(x for x in owned if not x.is_full())

    def nearest_ship_dist(e):
        return min(e.calculate_distance_between(ss) for ss in enemy_ships)
    
    unsafe = set(p for p in owned if nearest_ship_dist(p) < p.radius * 2.5)

    unowned = set(p for p in game_map.all_planets() if p not in owned)
    if len(unowned) == 0:
        command_queue.append(game_map.get_me().all_ships()[0].thrust(0,0))
        game.send_command_queue(command_queue)
        continue

    # interested_planets = unowned | nonfull | unsafe
    interested_planets = unowned | nonfull


    def ship_danger(e):
        if n_players == 4:
            if len(live_enemy_ships) <= 10:
                sample = live_enemy_ships
            else:
                sample = random.sample(live_enemy_ships, 10)
            d = sum((e.x-s.x)**2 + (e.y-s.y)**2 for s in sample)
            if d == 0:
                return 1
            else:
                return d ** -0.5
        
        else: # n_players == 2
            return 1
            # if len(live_enemy_ships) <= 10:
            #     sample = live_enemy_ships
            # else:
            #     sample = random.sample(live_enemy_ships, 10)
            # d = sum((e.x-s.x)**2 + (e.y-s.y)**2 for s in sample)
            # if d == 0:
            #     return 1
            # else:
            #     return d ** -0.1

    def pl_density_factor(p):
        return sum((p.x-pp.x)**2 + (p.y-pp.y)**2
                    for pp in game_map.all_planets()) ** 0.1

    def ship_planet_cost(s, p):
        return (s.calculate_distance_between(p)
                / p.num_docking_spots 
                * ship_danger(p)
                # * pl_density_factor(p)
                )
    
    def ship_ship_cost(s1, s2):
        return (s1.calculate_distance_between(s2) 
                * (0.5 / ship_ratio)
                * ship_danger(s2)
                )
    
    def best_ship(s):
        closest_ships = sorted(enemy_ships, key=lambda ss: s.calculate_distance_between(ss))[:5]
        return min(closest_ships, key=lambda ss: ship_ship_cost(s,ss))
    
    def nearest_planet(s):
        return min(interested_planets, key=lambda p: s.calculate_distance_between(p))
    def best_planet(s):
        closest_planets = sorted(interested_planets, key=lambda p: s.calculate_distance_between(p))[:5]
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
                return random.choice(x.all_docked_ships())
                # return iter(x.all_docked_ships()).__next__()
        elif type(x) == hlt.entity.Ship:
            return x
        else:
            return None

    closest_enemies = dict()
    for p in game_map.all_planets():
        closest_enemies[p.id] = min(
            live_enemy_ships, 
            key=lambda ss: p.calculate_distance_between(ss)
        )

    # checkpoint(-1)
    # for ship in sorted(live_ships, key=lambda s: s.calculate_distance_between(best_entity(s))):
    for i, ship in enumerate(sorted(live_ships, key=lambda s: s.calculate_distance_between(nearest_planet(s)))):
        checkpoint(i)
        if time.time() - t_start > 1.25:
            break

        cmd = None

        def my_navigate(ent):
            return ship.navigate(
                ship.closest_point_to(ent),
                game_map,
                speed=7,
                ignore_ships=False,
                max_corrections=50
            )
        
        np = nearest_planet(ship)
        be = None
        if can_dock(ship, np):
            closest_enemy = closest_enemies[np.id]
            if np.calculate_distance_between(closest_enemy) > np.radius*2.5 \
                    or np.owner == None:
                cmd = ship.dock(np)
                # logging.info("docking")
            else:
                # cmd = my_navigate(best_ship(ship))
                cmd = my_navigate(closest_enemy)
        else:
            be = best_entity(ship)
            cmd = my_navigate(get_target_around(be))

        if not cmd:
            # logging.info("fallback planner")
            if np.owner:
                if np.owner.id == my_id:
                    direction = math.atan2(ship.y-np.y, ship.x-np.x)
                else:
                    direction = math.atan2(np.y-ship.y, np.x-ship.x)
                x = ship.x + 1 * math.cos(direction)
                y = ship.y + 1 * math.sin(direction)
                faux_target = hlt.entity.Entity(x,y,0,0,0,0)
                if not game_map.obstacles_between(ship, faux_target, ignore=hlt.entity.Planet):
                    # logging.info("success")
                    cmd = ship.thrust(1, math.degrees(direction))
        
        if cmd:
            command_queue.append(cmd)

    if len(command_queue) == 0:
        command_queue.append(game_map.get_me().all_ships()[0].thrust(0,0))
    
    game.send_command_queue(command_queue)
