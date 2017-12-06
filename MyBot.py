import hlt
import logging
import time
import random
import numpy as np
import itertools
import collections
import math
from enum import Enum

class MyState(Enum):
    EARLY = 0
    NORMAL = 1
game_state = MyState.EARLY

prev_poses = dict()

game = hlt.Game("EB16")

while True:
    game_map = game.update_map()
    t_start = time.time()
    lastTime = t_start

    def checkpoint(msg):
        logging.info(msg + " - " + str(time.time()-t_start))

    def pos_dist(pos1, pos2):
        return ((pos1[0]-pos2[0])**2 + (pos1[1]-pos2[1])**2) ** 0.5

    def ent_dist(e1, e2):
        return e1.calculate_distance_between(e2)

    my_id = game_map.my_id
    n_players = len(game_map.all_players())
    command_queue = []
    nav_targets = dict()

    all_entities = game_map.all_planets() + game_map._all_ships()

    all_my_ships = list(game_map.get_me().all_ships())
    ship_radius = 0.8
    for s in all_my_ships:
        s.radius = ship_radius

    live_ships = [x for x in game_map.get_me().all_ships() if x.docking_status==x.DockingStatus.UNDOCKED]
    random.shuffle(live_ships)

    # my_clusters = list()
    # def get_cluster(ship):
    #     for cluster in my_clusters:
    #         if ship in cluster:
    #             return cluster
    #     return None

    # for ship in live_ships:
    #     for other in live_ships:
    #         if ship != other and ship.calculate_distance_between(other) < 2.0:
    #             other_cluster = get_cluster(other)
    #             if other_cluster:
    #                 other_cluster.add(ship)
    #             else:
    #                 my_clusters.append(set([ship]))
            


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

    should_deal_with_attackers = []
    if game_state == MyState.EARLY:
        if n_players != 2 or len(all_my_ships) != 3:
            game_state = MyState.NORMAL
            logging.info("leaving early game state")
        else:
            attackers = []
            for s in live_enemy_ships:
                if s in prev_poses:
                    dx = s.x - prev_poses[s].x
                    dy = s.y - prev_poses[s].y
                    h_travel = math.atan2(dy, dx)
                    for my_s in all_my_ships:
                        h_to_me = math.atan2(my_s.y-s.y, my_s.x-s.x)
                        attack_thresh = 0.5
                        towards = lambda h: h>h_to_me-attack_thresh and h<h_to_me+attack_thresh
                        if any(towards(h) for h in (h_travel, h_travel+math.pi*2, h_travel-math.pi*2)) \
                                and s not in attackers:
                            attackers.append(s)

            for sa in attackers:
                for sm in sorted(live_ships, key=lambda s: ent_dist(s,sa)):
                    if sm not in should_deal_with_attackers:
                        should_deal_with_attackers.append(sm)
                        break
            

    # is_2p_early_game = n_players == 2 and len(enemy_ships) == 3 \
    #                 and len(all_my_ships) == 3

    get_owner_id = lambda pl: pl.owner.id if pl.owner else -1

    owned = set(x for x in game_map.all_planets() if get_owner_id(x) == my_id)
    nonfull = set(x for x in owned if not x.is_full())

    def nearest_ship_dist(e):
        return min(e.calculate_distance_between(ss) for ss in live_enemy_ships)

    unowned = set(p for p in game_map.all_planets() if p not in owned)
    if len(unowned) == 0:
        command_queue.append(game_map.get_me().all_ships()[0].thrust(0,0))
        game.send_command_queue(command_queue)
        continue

    # interested_planets = unowned | nonfull | unsafe
    interested_planets = unowned | nonfull

    if n_players == 4:
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
        # logging.info("lowest centrality is %f" % min(centrality.values()))
        # logging.info("highest centrality is %f" % max(centrality.values()))

    pl_counts = collections.Counter()
    entity_counts = collections.Counter()

    planet_enemies = dict()
    planet_friendlies = dict()
    for p in game_map.all_planets():
        planet_enemies[p] = [s for s in live_enemy_ships
                if p.calculate_distance_between(s) < p.radius+40]
        planet_friendlies[p] = [s for s in live_ships
                if p.calculate_distance_between(s) < p.radius+40]

    def n_pl_targeting(pl):
        return pl_counts[pl] + len(pl.all_docked_ships())

    def ship_planet_cost(s, p):
        c = s.calculate_distance_between(p) / p.num_docking_spots
        if p in pl_counts:
            c *= math.exp(0.09 * n_pl_targeting(p))
        n = len(planet_enemies[p]) - len(planet_friendlies[p])
        c *= math.exp(0.08 * n)
        if game_state==MyState.NORMAL and not p.owner and p not in pl_counts \
                and planet_safe(p) and nearest_ship_dist(s) > 120:
            c *= 0.5
        if n_players == 4:
            c *= centrality[p]
        if game_state==MyState.EARLY and pl_counts[p]:
                if nearest_ship_dist(s) < 120:
                    c *= 0.01
                    # logging.info("enemies close, go to same planet")
                else:
                    c *= 1.3
                    # logging.info("enemies far, go to different planets")
        return c
    
    def ship_ship_cost(s1, s2):
        c = s1.calculate_distance_between(s2)
        if s2.docking_status!=s2.DockingStatus.UNDOCKED:
            c *= 0.13
        else:
            nearp = nearest_planet(s2)
            if get_owner_id(nearp)==my_id \
                    and len(planet_enemies[nearp]) <= len(planet_friendlies[nearp]):
                c *= 0.1
            else:
                c *= 1.5
        if entity_counts[s2]:
            c *= 0.7
        if n_players == 4:
            c *= centrality[s2]
        return c
    
    def best_ship(s):
        closest_ships = sorted(enemy_ships, key=lambda ss: s.calculate_distance_between(ss))[:15]
        return min(closest_ships, key=lambda ss: ship_ship_cost(s,ss))
    
    def nearest_planet(s):
        return min(interested_planets, key=lambda p: s.calculate_distance_between(p))
    def best_planet(s):
        # closest_planets = sorted(, key=lambda p: s.calculate_distance_between(p))
        return min(interested_planets, key=lambda p: ship_planet_cost(s,p))
    # def best_planet_list(s):
    #     return sorted(interested_planets, key=lambda p: ship_planet_cost(s,p))

    def best_entity(s):
        bs = best_ship(s)
        bp = best_planet(s)
        # logging.info("best planet %.3f" % ship_planet_cost(s,bp))
        # logging.info("best ship %.3f" % ship_ship_cost(s,bs))
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

    def collided(x, y, r, t, obs_list=None, ignore=tuple()):
        if not obs_list:
            obs_list = all_entities
        for obs in obs_list:
            if obs in nav_targets:
                ox = obs.x + (nav_targets[obs][0] - obs.x) * t
                oy = obs.y + (nav_targets[obs][1] - obs.y) * t
            else:
                ox, oy = obs.x, obs.y
            if ((x-ox)**2+(y-oy)**2) <= (r+obs.radius)**2 \
                    and (obs.x,obs.y) not in ignore:
                # logging.info("(%f, %f)"%(e.x,e.y))
                # logging.info(ignore)
                return True
        return False

    # def obstacles_between(pos1, pos2, ignore=tuple()):
    #     n = 7
    #     # obstacles = game_map.nearby_entities_by_distance(hlt.entity.Entity(pos2[0],pos2[1],0,0,0,0))[:8]
    #     obstacles = sorted(game_map.all_planets()+game_map._all_ships(), 
    #                         key=lambda o: o.calculate_distance_between(hlt.entity.Position(*pos2)))
    #     obstacles = obstacles[:8]
    #     for x,y,t in zip(np.linspace(pos1[0],pos2[0],n), 
    #                      np.linspace(pos1[1],pos2[1],n),
    #                      np.linspace(0.0, 1.0, n)):
    #         # e = hlt.entity.Entity(x, y, ship_radius+1, 1,0,-1)
    #         if collided(x, y, ship_radius, t, ignore=ignore, obs_list=obstacles):
    #             return True
    #     return False

    def obstacles_between(pos1, pos2, ignore=tuple()):
        vel_x = pos2[0] - pos1[0]
        vel_y = pos2[1] - pos1[1]
        mag = pos_dist(pos1, pos2)
        if mag > 7:
            vel_x, vel_y = 7*vel_x/mag, 7*vel_y/mag
        
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
            k = 3
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
                    costs[nextPos] = costs[thisPos] + 1 \
                        + 1 / nearest_ship_dist(hlt.entity.Position(*thisPos))
                    fringe.append((costs[nextPos] + (dist(nextPos)/7),
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
            if not collided(x, y, src.radius, 1, ignore=((src.x,src.y),)):
                return hlt.entity.Position(x,y)
            # logging.info("theta = %.2f collided" % theta)
            theta += math.pi / 10 if theta >= 0 else 0
            theta = -theta
        return None

    def planet_safe(pl):
        return len(planet_enemies[pl]) == 0 \
            or len(planet_friendlies[pl]) >= 1.5 * len(planet_enemies[pl])

    def is_planet(e):
        return type(e) == hlt.entity.Planet
    def is_ship(e):
        return type(e) == hlt.entity.Ship

    # original_target is a (x,y) tuple
    def micro_policy(ship, original_target):
        near_friends = [s for s in live_ships 
                        if ship.calculate_distance_between(s) <= 30]
        near_live_enemies = [s for s in live_enemy_ships 
                             if ship.calculate_distance_between(s) <= 30]

        if len(near_live_enemies) == 0 or len(near_friends) > len(near_live_enemies):
            return original_target

        def h(p):
            want_close = pos_dist(original_target, p) if original_target else 0
            if near_friends:
                want_close += min(ship.calculate_distance_between(ss) for ss in near_friends)
            e = hlt.entity.Position(p[0], p[1])
            closest = min(near_live_enemies, key=lambda ss: e.calculate_distance_between(ss))
            avoid_pos = (closest.x, closest.y)
            if n_players==4 and ship_ratio < 1/4:
                runaway_k = 5
            else:
                runaway_k = 1.2
            return pos_dist(avoid_pos, p)*runaway_k - want_close

        thrusts = [7,5,3,1]
        angles = np.arange(0, 2*math.pi, math.pi/12)
        pos1 = (ship.x, ship.y)
        best_pos = pos1
        best_sep = h(pos1)
        for t,a in itertools.product(thrusts, angles):
            pos2 = ship.x+t*math.cos(a), ship.y+t*math.sin(a)
            if not obstacles_between(pos1, pos2, ignore=(pos1,)) \
                    and h(pos2) > best_sep \
                    and inbounds(pos2):
                best_pos = pos2
                best_sep = h(pos2)
        return best_pos


    ship_entity_combos = []
    for s in sorted(live_ships, 
                    key=lambda ss: nearest_planet(ss).calculate_distance_between(ss)):
        be = best_entity(s)
        entity_counts[be] += 1
        if is_planet(be):
            pl_counts[be] += 1
        ship_entity_combos.append((be, s))
    
    # dock ships that can
    docking = set()
    for best_entity, ship in ship_entity_combos:
        if is_planet(best_entity) \
                and can_dock(ship, best_entity) \
                and planet_safe(best_entity):
            # if is_2p_early_game and nearest_ship_dist(ship) < 150 \
            #         and len(live_enemy_ships) >= len(live_ships) - len(docking):
            #     continue
            if game_state == MyState.EARLY and (
                    ship in should_deal_with_attackers
                    or nearest_ship_dist(ship) < 30
            ):
                continue
            command_queue.append(ship.dock(best_entity)) 
            docking.add(ship)

    # for ship in sorted(live_ships, key=lambda s: s.calculate_distance_between(best_entity(s))):
    for i, (best_entity, ship) in enumerate(sorted(ship_entity_combos, 
                            key=lambda sec: sec[1].calculate_distance_between(sec[0]))):
        if time.time() - t_start > 1.3:
            break

        if ship not in docking:
            if n_players == 2 and ship.id == min(s.id for s in live_ships):
                if len(enemy_ships) == len(live_enemy_ships):
                    greedy = min(enemy_ships, key=lambda s: ship.calculate_distance_between(s))
                else:
                    greedy = min((s for s in enemy_ships if s.docking_status!=s.DockingStatus.UNDOCKED),
                                      key=lambda s: ship.calculate_distance_between(s))

            if is_planet(best_entity):
                if not planet_safe(best_entity):
                    best_entity = min(
                        planet_enemies[best_entity],
                        key=lambda s: best_entity.calculate_distance_between(s)
                    )

            target_entity = get_target_around(best_entity)

            if is_ship(best_entity) \
                    and ship.health < best_entity.health:
                navTarget = target_entity
            else:
                navTarget = closest_point(ship, target_entity)
            if navTarget:
                timeLimit = 0.04
                nextPos = search((ship.x, ship.y), (navTarget.x, navTarget.y), timeLimit)
                nextPos = micro_policy(ship, nextPos)
                if nextPos:
                    nx, ny = nextPos
                    mag = min(7, ((nx-ship.x)**2 + (ny-ship.y)**2)**0.5)
                    cmd = ship.thrust(int(mag), math.degrees(math.atan2(ny-ship.y, nx-ship.x))%360)
                    command_queue.append(cmd)
                    nav_targets[ship] = nextPos
                else:
                    a = min(set(game_map.all_planets()) | set(live_ships) - set((ship,)), 
                            key=lambda s: ship.calculate_distance_between(s))
                    angle = a.calculate_angle_between(ship)
                    cmd = ship.thrust(3, angle)
                    nx += 3 * math.cos(math.radians(angle))
                    ny += 3 * math.sin(math.radians(angle))
                    command_queue.append(cmd)
                    nav_targets[ship] = (nx, ny)

    if len(command_queue) == 0:
        command_queue.append(game_map.get_me().all_ships()[0].thrust(0,0))
    
    game.send_command_queue(command_queue)

    # time.sleep(min(1.9-time.time()+t_start, 1.0))
