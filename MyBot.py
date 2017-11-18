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
    lastTime = t_start

    def checkpoint(msg):
        logging.info(msg + " - " + str(time.time()-t_start))

    my_id = game_map.my_id
    n_players = len(game_map.all_players())
    command_queue = []

    all_my_ships = list(game_map.get_me().all_ships())
    ship_radius = 1
    for s in all_my_ships:
        s.radius = ship_radius

    live_ships = [x for x in game_map.get_me().all_ships() if x.docking_status==x.DockingStatus.UNDOCKED]

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

    enemy_ships = []
    for player in game_map.all_players():
        if player.id != my_id:
            enemy_ships += player.all_ships()

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

    def collided(x, y, r, obs_list=None, ignore=tuple()):
        if not obs_list:
            obs_list = itertools.chain(game_map.all_planets(), game_map._all_ships())
        for obs in obs_list:
            if ((x-obs.x)**2+(y-obs.y)**2) <= (r+obs.radius)**2 \
                    and (obs.x,obs.y) not in ignore:
                # logging.info("(%f, %f)"%(e.x,e.y))
                # logging.info(ignore)
                return True
        return False

    def obstacles_between(pos1, pos2, ignore=tuple()):
        n = 5
        # obstacles = game_map.nearby_entities_by_distance(hlt.entity.Entity(pos2[0],pos2[1],0,0,0,0))[:8]
        obstacles = sorted(game_map.all_planets()+game_map._all_ships(), 
                            key=lambda o: o.calculate_distance_between(hlt.entity.Position(*pos2)))
        obstacles = obstacles[:8]
        for x,y in zip(np.linspace(pos1[0],pos2[0],n), np.linspace(pos1[1],pos2[1],n)):
            e = hlt.entity.Entity(x, y, ship_radius+1, 1,0,-1)
            if collided(x, y, ship_radius, ignore=ignore, obs_list=obstacles):
                return True
        return False
        # e1 = hlt.entity.Entity(pos1[0],pos1[1],ship_radius,1,0,-1)
        # e2 = hlt.entity.Entity(pos2[0],pos2[1],ship_radius,1,0,-2)
        # logging.info(str(e1) + ", " + str(e2))
        # for o in game_map.obstacles_between(e1, e2):
            # if (o.x,o.y) not in ignore:
                # return True
        # return False

    inbounds = lambda pos: pos[0]>ship_radius and pos[0]<game_map.width-ship_radius \
                       and pos[1]>ship_radius and pos[1]<game_map.height-ship_radius

    def succ(pos, ignore=tuple()):
        out = []
        theta = 0
        for r in (7,5,3):
            while theta < 2*math.pi-0.0001:
                p2 = pos[0] + r*math.cos(theta), pos[1] + r*math.sin(theta)
                if inbounds(p2) \
                        and not obstacles_between(pos, p2, ignore=ignore):
                    out.append(p2)
                    # logging.info(str(pos) + " -> " + str(p2) + ", theta = " + str(theta))
                theta += math.pi / 8
        return out
    
    # logging.info(str(succ((20, 20))))
    
    def search(pos1, pos2):
        def dist(p):
            return ((p[0]-pos2[0])**2+(p[1]-pos2[1])**2)**0.5

        searchTimeStart = time.time()
        timeLimit = 1.25 / len(live_ships)
        fringe = [(0, pos1[0], pos1[1])]
        visited = set()
        def visit(x,y):
            k = 4
            if (x//k, y//k) in visited:
                return True
            visited.add((x//k, y//k))
            return False
        costs = dict()
        costs[pos1] = 0
        parents = dict()
        while len(fringe) > 0 and time.time()-searchTimeStart < timeLimit:
            _, thisX, thisY = fringe.pop( np.argmin(fringe, axis=0)[0] )
            thisPos = (thisX, thisY)
            # logging.info("len(fringe) = %d" % len(fringe))
            if dist(thisPos) <= 7 \
                    and not obstacles_between(thisPos, pos2, ignore=(pos1,)):
                parents[pos2] = thisPos
                break
            if visit(thisX, thisY):
                continue
            for nextPos in succ(thisPos, ignore=(pos1,)):
                if (nextPos not in costs) or (costs[thisPos]+1 < costs[nextPos]):
                    costs[nextPos] = costs[thisPos] + 1
                    fringe.append((costs[thisPos]+1+(dist(nextPos)/7),
                                    nextPos[0], nextPos[1]))
                    parents[nextPos] = thisPos
        pos = pos2 if pos2 in parents else min(costs.keys(), key=dist)
        while pos in parents:
            if parents[pos] == pos1:
                return pos
            pos = parents[pos]
        logging.info("found no route from %s to %s"%(str(pos1),str(pos2)))
        return None

    def closest_point(src, dst):
        theta = 0
        r = src.radius + dst.radius + 1
        travel_angle = math.atan2(src.y-dst.y, src.x-dst.x)
        idealX = dst.x + r * math.cos(travel_angle)
        idealY = dst.y + r * math.sin(travel_angle)
        phi = travel_angle + math.pi
        while theta < math.pi:
            x = idealX + r * (math.cos(phi) - math.cos(phi+theta))
            y = idealY + r * (math.sin(phi) - math.sin(phi+theta))
            if not collided(x, y, src.radius, ignore=((src.x,src.y),)):
                return hlt.entity.Entity(x,y,src.radius,0,0,0)
            logging.info("theta = %.2f collided" % theta)
            theta += math.pi / 10 if theta >= 0 else 0
            theta = -theta
        return None


    random.shuffle(live_ships)
    ship_entity_combos = [(best_entity(s),s) for s in live_ships]
    # for ship in sorted(live_ships, key=lambda s: s.calculate_distance_between(best_entity(s))):
    for i, (best_entity, ship) in enumerate(sorted(ship_entity_combos, 
                            key=lambda sec: sec[1].calculate_distance_between(sec[0]))):
        if time.time() - t_start > 1.25:
            break

        if type(best_entity)==hlt.entity.Planet \
                and can_dock(ship, best_entity):
            command_queue.append(ship.dock(best_entity))
        else:
            checkpoint(str(i))
            navTarget = closest_point(ship, get_target_around(best_entity))
            if navTarget:
                nextPos = search( (ship.x, ship.y), (navTarget.x, navTarget.y) )
                if nextPos:
                    nx, ny = nextPos
                    mag = min(7, ((nx-ship.x)**2 + (ny-ship.y)**2)**0.5)
                    cmd = ship.thrust(int(mag), math.degrees(math.atan2(ny-ship.y, nx-ship.x)))
                    ship.x = nx
                    ship.y = ny

                    command_queue.append(cmd)
            # checkpoint("after navigate")

    if len(command_queue) == 0:
        command_queue.append(game_map.get_me().all_ships()[0].thrust(0,0))
    
    game.send_command_queue(command_queue)

    # time.sleep(min(1.9-time.time()+t_start, 1.0))
