import hlt
import logging
import time
import random
import numpy as np
import cv2
import itertools
import math

game = hlt.Game("EB5")

def ship_planet_cost(s, p):
    return s.calculate_distance_between(p) / p.num_docking_spots

cv2.namedWindow("test")

while True:
    t_start = time.time()
    game_map = game.update_map()
    my_id = game_map.my_id
    command_queue = []

    live_ships = [x for x in game_map.get_me().all_ships() if x.docking_status == x.DockingStatus.UNDOCKED]

    get_owner_id = lambda pl: pl.owner.id if pl.owner else -1

    owned = [x for x in game_map.all_planets() if get_owner_id(x) == my_id]
    nonfull = [x for x in owned if not x.is_full()]
    if len(owned) == 0:
        owned += live_ships
    unowned = [x for x in game_map.all_planets() if get_owner_id(x) != my_id]
    if len(unowned) == 0:
        game.send_command_queue([])
        continue
    
    def nearest_planet(s):
        return min(unowned+nonfull, key=lambda p: s.calculate_distance_between(p))
    def best_planet(s):
        return min(unowned+nonfull, key=lambda p: ship_planet_cost(s,p))
    
    arrived = [x for x in live_ships if x.can_dock(best_planet(x))]
    unarrived = [x for x in live_ships if not x.can_dock(best_planet(x))]

    arrived_leftover = []
    for ship in arrived:
        tpl = nearest_planet(ship)
        if tpl.is_full():
            arrived_leftover.append(ship)
        else:
            command_queue.append(ship.dock(tpl))

    def get_target_around_planet(tpl):
        if get_owner_id(tpl) in (-1, my_id):
            return tpl
        else:
            return iter(tpl.all_docked_ships()).__next__()

    def fill_entity(grid, e, n):
        grid_height, grid_width = grid.shape
        scale_factor = grid_width / game_map.width
        for x in range(int(max(0, round(e.x-e.radius))), int(min(game_map.width, round(e.x+e.radius)))):
            x = x * scale_factor
            for y in range(int(max(0, round(e.y-e.radius))), int(min(game_map.height, round(e.y+e.radius)))):
                y = y * scale_factor
                dist = ((e.x*scale_factor - x)**2 + (e.y*scale_factor - y)**2) ** 0.5
                if dist <= e.radius*scale_factor:
                    grid[min(int(y),grid_height-1), min(int(x),grid_width-1)] = n

    def in_bounds(grid,x,y):
        return x>=0 and x<grid.shape[1] and y>=0 and y<grid.shape[0]
    
    def neighbors(grid,x,y):
        dxy = ((0,-1), (1,-1), (1,0), (1,1), (0,1), (-1,1), (-1,0), (-1,-1))
        return [(x+dx, y+dy) for dx,dy in dxy if in_bounds(grid,x+dx,y+dy)]


    def watershed():
        width = game_map.width #80
        height = game_map.height #45
        grid = np.full((height, width), 255, dtype=np.uint8)
        
        # root = hlt.entity.Entity(0,0,1,1,-1,-1)
        enemy_ships = [s for s in game_map._all_ships() if s.owner != my_id]
        r_planet = 0
        r_ship = 5
        for p in unowned + nonfull:
            fill_entity(grid, p, r_planet)
        for s in enemy_ships:
            fill_entity(grid, s, r_ship)

        frontier = list(zip(*np.nonzero(grid != grid.max())))
        while len(frontier) > 0:
            y0,x0 = frontier.pop(0)
            for x1,y1 in neighbors(grid,x0,y0):
                if grid[y1,x1] > grid[y0,x0] + 1:
                    grid[y1,x1] = grid[y0,x0] + 1
                    frontier.append((y1,x1))

        for entity in game_map._all_ships() + game_map.all_planets():
            fill_entity(grid, entity, 255)
        
        return grid

    # logging.info(time.time() - t_start)

    t = time.time()
    grid = watershed()
    cv2.imshow("test", grid*5)
    k = cv2.waitKey(1) & 0xFF
    if k == 27:
        cv2.destroyAllWindows()
        break

    logging.info(time.time() - t)

    grid_height, grid_width = grid.shape
    scale_factor = grid_width / game_map.width

    # i = 0
    # for ship in sorted(unarrived, key=lambda s: s.calculate_distance_between(best_planet(s))):
    for ship in unarrived:
        cmd = None
        
        # i+=1
        if time.time() - t_start < 1.25:
            # cmd = ship.navigate(
            #     ship.closest_point_to(get_target_around_planet(best_planet(ship))), 
            #     game_map, 
            #     speed=hlt.constants.MAX_SPEED, 
            #     ignore_ships=False,
            #     max_corrections=100
            # )
            xg0 = min(int(ship.x*scale_factor), grid_width-1)
            yg0 = min(int(ship.y*scale_factor), grid_height-1)
            xg1, yg1 = min(neighbors(grid, xg0, yg0), key=lambda pos: grid[pos[1],pos[0]])
            angle = math.degrees(math.atan2(yg1-yg0, xg1-xg0))
            cmd = ship.thrust(7, angle)
        if cmd:
            command_queue.append(cmd)

    if len(command_queue) == 0 and len(live_ships) > 0:
        command_queue.append(live_ships[0].thrust(0,0))
    game.send_command_queue(command_queue)
