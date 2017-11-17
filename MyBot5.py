import hlt
import logging
import time
import random
import numpy as np
import itertools
import math

game = hlt.Game("EB5")

LOG = True

while True:
    game_map = game.update_map()
    t_start = time.time()

    def checkpoint(ii):
        if LOG:
            logging.info("%d - %f" % (ii, time.time() - t_start))

    my_id = game_map.my_id
    n_players = len(game_map.all_players())
    command_queue = []

    all_my_ships = list(game_map.get_me().all_ships())
    for s in all_my_ships:
        s.radius = 1.0

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
    
    # dockable = set(x for x in live_ships if can_dock(x, best_planet(x)))
    # undockable = set(live_ships) - dockable
    # logging.info((len(dockable), len(undockable)))

    # arrived_leftover = []
    # for ship in dockable:
    #     command_queue.append(ship.dock(nearest_planet(ship)))

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

    # def fill_entity(grid, e, n):
    #     grid_height, grid_width = grid.shape
    #     scale_factor = grid_width / game_map.width
    #     for x in range(int(max(0, round(e.x-e.radius))), int(min(game_map.width, round(e.x+e.radius)))):
    #         x = x * scale_factor
    #         for y in range(int(max(0, round(e.y-e.radius))), int(min(game_map.height, round(e.y+e.radius)))):
    #             y = y * scale_factor
    #             dist = ((e.x*scale_factor - x)**2 + (e.y*scale_factor - y)**2) ** 0.5
    #             if dist <= e.radius*scale_factor:
    #                 grid[min(int(y),grid_height-1), min(int(x),grid_width-1)] = n

    # def in_bounds(grid,x,y):
    #     return x>=0 and x<grid.shape[1] and y>=0 and y<grid.shape[0]
    
    # def neighbors(grid,x,y):
    #     dxy = ((0,-1), (1,-1), (1,0), (1,1), (0,1), (-1,1), (-1,0), (-1,-1))
    #     return [(x+dx, y+dy) for dx,dy in dxy if in_bounds(grid,x+dx,y+dy)]


    # def discretize():
    #     width = game_map.width
    #     height = game_map.height
    #     grid = np.zeros((height, width), dtype=np.float64)
        
    #     # root = hlt.entity.Entity(0,0,1,1,-1,-1)
    #     enemy_ships = [s for s in game_map._all_ships() if s.owner != my_id]
    #     r_planet = 0
    #     r_ship = 5
    #     for p in unowned + nonfull:
    #         fill_entity(grid, p, r_planet)
    #     for s in enemy_ships:
    #         fill_entity(grid, s, r_ship)

    #     frontier = list(zip(*np.nonzero(grid != grid.max())))
    #     while len(frontier) > 0:
    #         y0,x0 = frontier.pop(0)
    #         for x1,y1 in neighbors(grid,x0,y0):
    #             if grid[y1,x1] > grid[y0,x0] + 1:
    #                 grid[y1,x1] = grid[y0,x0] + 1
    #                 frontier.append((y1,x1))

    #     for entity in game_map._all_ships() + game_map.all_planets():
    #         fill_entity(grid, entity, 255)
        
    #     return grid

    # logging.info(time.time() - t_start)


    # grid_height, grid_width = grid.shape
    # scale_factor = grid_width / game_map.width

    # i = 0
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
