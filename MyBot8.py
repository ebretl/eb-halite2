import hlt
import logging
import time
import random
import numpy as np
import itertools
import collections
import math

game = hlt.Game("EB8")

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
    ship_radius = 1.2
    for s in all_my_ships:
        s.radius = ship_radius

    live_ships = [x for x in game_map.get_me().all_ships() if x.docking_status==x.DockingStatus.UNDOCKED]
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

    centrality = collections.Counter()
    entities = game_map.all_planets() + enemy_ships
    for e_src, e_cmp in itertools.permutations(entities, 2):
        if type(e_cmp) == hlt.entity.Ship \
                and e_cmp.docking_status!=e_cmp.DockingStatus.UNDOCKED:
            continue
        c = math.exp(-0.05 * e_src.calculate_distance_between(e_cmp))
        centrality[e_src] += c
    avg = sum(centrality.values()) / len(centrality)
    for e, score in centrality.items():
        centrality[e] = (score / avg) ** 0.5
    logging.info("lowest centrality is %f" % min(centrality.values()))
    logging.info("highest centrality is %f" % max(centrality.values()))

    # planet_costs = collections.Counter()
    # for p1, p2 in itertools.permutations(game_map.all_planets(), 2):
    #     planet_costs[p1] += p1.calculate_distance_between(p2) \
    #                         / p1.num_docking_spots
    # max_score = max(planet_costs.values())
    # for p, score in planet_costs.items():
    #     planet_costs[p] = math.exp(score / max_score)
    # #     logging.info(p)
    # #     logging.info(score)
    # #     logging.info(score / max_score)
    # logging.info("best planet score is %f" % min(planet_costs.values()))
    # logging.info("worst planet score is %f" % max(planet_costs.values()))

    # ship_costs = collections.Counter()
    # for s1, s2 in itertools.permutations(enemy_ships, 2):
    #     if s2.docking_status == s2.DockingStatus.UNDOCKED:
    #         ship_costs[s1] += s1.calculate_distance_between(s2)
    # max_score = max(ship_costs[s] for s in enemy_ships)
    # for s, score in ship_costs.items():
    #     if max_score > 0:
    #         ship_costs[s] = math.exp(score / max_score)
    #     else:
    #         ship_costs[s] = math.exp(1)
    # logging.info("best ship score is %f" % min(ship_costs[s] for s in enemy_ships))
    # logging.info("worst ship score is %f" % max(ship_costs[s] for s in enemy_ships))


    def ship_planet_cost(s, p):
        c = s.calculate_distance_between(p) / p.num_docking_spots 
        if n_players == 2:
            return c
        else:
            return c * centrality[p]
    
    def ship_ship_cost(s1, s2):
        c = s1.calculate_distance_between(s2) * 0.7
        if s2.docking_status==s2.DockingStatus.UNDOCKED:
            c *= 0.5
        if n_players == 2:
            return c
        else:
            return c * centrality[s2]
    
    def best_ship(s):
        closest_ships = sorted(enemy_ships, key=lambda ss: s.calculate_distance_between(ss))[:15]
        return min(closest_ships, key=lambda ss: ship_ship_cost(s,ss))
    
    def nearest_planet(s):
        return min(interested_planets, key=lambda p: s.calculate_distance_between(p))
    def best_planet(s):
        # closest_planets = sorted(, key=lambda p: s.calculate_distance_between(p))
        return min(interested_planets, key=lambda p: ship_planet_cost(s,p))

    def best_entity(s):
        bs = best_ship(s)
        bp = best_planet(s)
        logging.info("best planet %.3f" % ship_planet_cost(s,bp))
        logging.info("best ship %.3f" % ship_ship_cost(s,bs))
        return bs if ship_ship_cost(s,bs) < ship_planet_cost(s,bp) else bp

    def can_dock(s, p):
        return s.can_dock(p) and (not p.is_full()) and (get_owner_id(p) in (-1, my_id))

    def get_target_around(x):
        if type(x) == hlt.entity.Planet:
            if get_owner_id(x) in (-1, my_id):
                return x
            else:
                # return random.choice(x.all_docked_ships())
                # return iter(x.all_docked_ships()).__next__()
                return min(x.all_docked_ships(), 
                        key=lambda s: x.calculate_distance_between(s))
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
                if inbounds(p2):
                    out.append(p2)
                    # logging.info(str(pos) + " -> " + str(p2) + ", theta = " + str(theta))
                theta += math.pi / 8
        return out
    
    # logging.info(str(succ((20, 20))))
    
    def search(pos1, pos2, timeLimit=0.1):
        def dist(p):
            return ((p[0]-pos2[0])**2+(p[1]-pos2[1])**2)**0.5

        searchTimeStart = time.time()
        fringe = [(0, pos1[0], pos1[1])]
        visited = set()
        def visit(pos, update=False):
            k = 4
            if (pos[0]//k, pos[1]//k) in visited:
                return True
            if update:
                visited.add((pos[0]//k, pos[1]//k))
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
            if visit(thisPos, update=True):
                continue
            for nextPos in succ(thisPos, ignore=(pos1,)):
                if (not visit(nextPos, update=False)) \
                        and (
                            (not nextPos in costs) 
                            or (costs[thisPos]+1 < costs[nextPos])
                        ):
                    if obstacles_between(thisPos, nextPos, ignore=(pos1,)):
                        continue
                    costs[nextPos] = costs[thisPos] + 1
                    fringe.append((costs[thisPos]+1+(dist(nextPos)/7),
                                    nextPos[0], nextPos[1]))
                    parents[nextPos] = thisPos
        pos = pos2 if pos2 in parents else min(costs.keys(), key=dist)
        while pos in parents:
            if parents[pos] == pos1:
                return pos
            pos = parents[pos]
        # logging.info("found no route from %s to %s"%(str(pos1),str(pos2)))
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
            # logging.info("theta = %.2f collided" % theta)
            theta += math.pi / 10 if theta >= 0 else 0
            theta = -theta
        return None

    closest_enemies = dict()
    for p in game_map.all_planets():
        closest_enemies[p.id] = min(
            live_enemy_ships, 
            key=lambda ss: p.calculate_distance_between(ss)
        )

    def planet_safe(pl):
        return pl.calculate_distance_between(
                closest_enemies[pl.id]) > pl.radius*3

    # def avoid(ship, original_target):
    #     def h(pos):
    #         return (ship.x - original_target.x) ** 2 \
    #              + (ship.y - original_target.y) ** 2
    #     thrusts = list(range(1,8))
    #     angles = list(range(0, 2*math.pi, math.pi/10))
    #     pos1 = (ship.x, ship.y)
    #     best_move = (0, 0)
    #     best_h = h((ship.x, ship.y))
    #     for t,a in itertools.product(thrusts, angles):
    #         pos2 = ship.x+t*math.cos(a), ship.y+t*math.sin(a)
    #         if not obstacles_between(pos1, pos2, ignore=(pos1,)) \
    #                 and h(pos2) < best_h:
    #             best_move = (t,a)
    #             best_h = h(pos2)
    #     return best_move


    ship_entity_combos = [(best_entity(s),s) for s in live_ships]

    # dock ships that can
    docking = set()
    for best_entity, ship in ship_entity_combos:
        if type(best_entity)==hlt.entity.Planet \
                and can_dock(ship, best_entity) \
                and (planet_safe(best_entity)
                    or best_entity.owner == None):
            command_queue.append(ship.dock(best_entity))
            docking.add(ship)

    # target_counts = collections.Counter()

    # for ship in sorted(live_ships, key=lambda s: s.calculate_distance_between(best_entity(s))):
    for i, (best_entity, ship) in enumerate(sorted(ship_entity_combos, 
                            key=lambda sec: sec[1].calculate_distance_between(sec[0]))):
        if time.time() - t_start > 1.25:
            break

        if ship not in docking:
            checkpoint(str(i))
            if type(best_entity)==hlt.entity.Planet \
                    and not planet_safe(best_entity):
                best_entity = closest_enemies[best_entity.id]
            target_entity = get_target_around(best_entity)

            if type(best_entity)==hlt.entity.Ship \
                    and ship.health < best_entity.health:
                navTarget = target_entity
            else:
                navTarget = closest_point(ship, target_entity)
            if navTarget:
                timeLimit = 0.04
                nextPos = search((ship.x, ship.y), (navTarget.x, navTarget.y), timeLimit)
                if nextPos:
                    nx, ny = nextPos
                    mag = min(7, ((nx-ship.x)**2 + (ny-ship.y)**2)**0.5)
                    cmd = ship.thrust(int(mag), math.degrees(math.atan2(ny-ship.y, nx-ship.x))%360)
                    ship.x = nx
                    ship.y = ny
                    command_queue.append(cmd)
                else:
                    a = min(set(game_map.all_planets()) | set(live_ships) - set((ship,)), 
                            key=lambda s: ship.calculate_distance_between(s))
                    # logging.info(ship)
                    # logging.info(a)
                    # logging.info(a.calculate_angle_between(ship))
                    # logging.info("")
                    angle = a.calculate_angle_between(ship)
                    cmd = ship.thrust(3, angle)
                    ship.x += 3 * math.cos(math.radians(angle))
                    ship.y += 3 * math.sin(math.radians(angle))
                    command_queue.append(cmd)

    if len(command_queue) == 0:
        command_queue.append(game_map.get_me().all_ships()[0].thrust(0,0))
    
    game.send_command_queue(command_queue)

    # time.sleep(min(1.9-time.time()+t_start, 1.0))
