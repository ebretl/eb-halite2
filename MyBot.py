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
turn_num = 0

game = hlt.Game("EB17")

while True:
    game_map = game.update_map()
    t_start = time.time()
    lastTime = t_start
    turn_num += 1
    logging.info("--- turn %d ---" % turn_num)

    def checkpoint(msg):
        logging.info(msg + " - " + str(time.time()-t_start))

    def pos_dist(pos1, pos2):
        return ((pos1[0]-pos2[0])**2 + (pos1[1]-pos2[1])**2) ** 0.5

    def ent_dist(e1, e2):
        return e1.calculate_distance_between(e2)

    my_id = game_map.my_id
    n_players = sum(1 if play.all_ships() else 0 for play in game_map.all_players())
    command_queue = []
    nav_targets = dict()

    def opt_dist(e1,e2):
        p1 = nav_targets[e1] if e1 in nav_targets else (e1.x,e1.y)
        p2 = nav_targets[e2] if e2 in nav_targets else (e2.x,e2.y)
        return pos_dist(p1, p2)

    # logging.info(str(n_players))

    all_entities = game_map.all_planets() + game_map._all_ships()

    all_my_ships = list(game_map.get_me().all_ships())
    ship_radius = 0.62
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
        live_enemy_ships.append(hlt.entity.Ship(-1,-1,-1000,-1000,0,0,0,-1,None,-1,-1))

    ship_ratio = len(all_my_ships) / most_enemy_ships

    def ent_enemies(e, x):
        return [s for s in live_enemy_ships if ent_dist(e, s) < e.radius + x]
    def ent_friendlies(e, x):
        return [s for s in live_ships if opt_dist(e, s) < e.radius + x]

    def compare_angle(h1, h2, thresh):
        pi2 = 2 * math.pi
        a1 = (h2 - h1) % pi2
        a2 = pi2 - a1
        return min(a1, a2) < thresh

    should_deal_with_attackers = set()
    should_gang_up = set()
    should_avoid_attackers = set()
    gang_up_target = None
    attackers_last_time = True
    if game_state == MyState.EARLY:
        # if n_players != 2 or len(all_my_ships) != 3:
        if len(enemy_ships) > 3 or len(live_ships) > 6 \
                or (len(live_enemy_ships) == 1 and live_enemy_ships[0].x<0):
            game_state = MyState.NORMAL
            logging.info("leaving early game state due to ship counts")
        else:
            attackers = dict() # ship -> heading
            for s in live_enemy_ships:
                if s.id in prev_poses and s not in attackers:
                    dx = s.x - prev_poses[s.id][0]
                    dy = s.y - prev_poses[s.id][1]
                    # logging.info("dy = %f, dx = %f" % (dy,dx))
                    h_travel = math.atan2(dy, dx)
                    mag_travel = (dx*dx+dy*dy)**0.5
                    for my_s in all_my_ships:
                        h_to_me = math.atan2(my_s.y-s.y, my_s.x-s.x)
                        if compare_angle(h_travel, h_to_me, 0.7) \
                                and mag_travel > 1 and ent_dist(s,my_s) < 150:
                            # logging.info("%f ~ %f" % (h_travel, h_to_me))
                            attackers[s] = h_travel
                            break
                    # logging.info("(%.2f, %.2f) over (%.2f, %.2f)" % ((s.x,s.y)+prev_poses[s.id]))
                prev_poses[s.id] = (float(s.x), float(s.y))

            if not attackers_last_time and not attackers:
                game_state = MyState.NORMAL
                logging.info("leaving early game state due to no attackers")
            attackers_last_time = bool(attackers)

            for sa, h in attackers.items():
                free = lambda ss: ss not in should_deal_with_attackers | should_avoid_attackers
                free_l = [ss for ss in live_ships if free(ss)]
                if len(free_l) > 0:
                    sm = min(free_l, key=lambda s: ent_dist(s,sa))
                    h_to_me = math.atan2(sm.y-s.y, sm.x-s.x)
                    if compare_angle(h, h_to_me, 1.2) and ent_dist(sa,sm)<150:
                        should_deal_with_attackers.add(sm)
                    else:
                        should_avoid_attackers.add(sm)
                    logging.info("%d wary of enemy %d" % (sm.id, sa.id))

            if len(attackers) > 1 and len(should_deal_with_attackers) > 1:
                for sa, h in attackers.items():
                    for sm in should_deal_with_attackers:
                        h_to_me = math.atan2(sm.y-s.y, sm.x-s.x)
                        other = min((x for x in attackers if x!=sa),
                                    key = lambda ss: ent_dist(sm,ss))
                        h_from_other = math.atan2(sm.y-other.y, sm.x-other.x)
                        friend = min((x for x in should_deal_with_attackers if x!=sm),
                                     key = lambda ss: ent_dist(sm,ss))
                        potential_target = min([sa, other], key=lambda ss: ss.health)
                        # logging.info("%f %f %f %d" % (ent_dist(sm, friend), 
                                                   # ent_dist(sm, potential_target),
                                                   # ent_dist(friend, potential_target),
                                                   # len(ent_enemies(potential_target, 7))))
                        if ent_dist(sm, friend) < 8 \
                                and ent_dist(sm, potential_target) < 15 \
                                and ent_dist(friend, potential_target) < 15 \
                                and not compare_angle(h_to_me, h_from_other, 1.5) \
                                and len(ent_enemies(potential_target, 7)) == 1 \
                                and sm not in should_gang_up \
                                and friend not in should_gang_up \
                                and not gang_up_target:
                            should_gang_up.add(sm)
                            should_gang_up.add(friend)
                            gang_up_target = potential_target
                            logging.info("gang up")
            

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

    if n_players != 2:
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

    def planet_safe(pl, n_dock=0):
        x = 30
        return len(ent_enemies(pl, x)) == 0 \
            or len(ent_friendlies(pl, x)) - n_dock >= 1.5 * len(ent_enemies(pl, x))


    # unsafe = set(p for p in owned if not planet_safe(p))
    # interested_planets = unowned | nonfull | unsafe
    interested_planets = unowned | nonfull

    def n_pl_targeting(pl):
        return pl_counts[pl] + len(pl.all_docked_ships())

    def ship_planet_cost(s, p):
        c = s.calculate_distance_between(p) / p.num_docking_spots
        if p in pl_counts:
            c *= math.exp(0.09 * n_pl_targeting(p))
        n = len(ent_enemies(p,30)) - len(ent_friendlies(p,30))
        c *= math.exp(0.08 * n)
        if game_state==MyState.NORMAL and not p.owner and p not in pl_counts \
                and nearest_ship_dist(p) > 120 and nearest_ship_dist(s) > 120:
            c *= 0.5
        # if get_owner_id(p)==my_id and not planet_safe(p):
        #     c *= 0.2
        if n_players != 2:
            c *= centrality[p]
        if game_state==MyState.EARLY and pl_counts[p]:
            if min(ent_dist(s,ss) for ss in enemy_ships) < 120:
                c *= 0.01
                # logging.info("enemies close, go to same planet")
            else:
                c *= 1.3
                # logging.info("enemies far, go to different planets")
        return c
    
    def ship_ship_cost(s1, s2):
        c = s1.calculate_distance_between(s2)
        if s2.docking_status != s2.DockingStatus.UNDOCKED:
            c *= 0.1
        else:
            c *= 1.5
            if len(owned) > 0:
                d = min(ent_dist(s2,p) for p in owned)
                n = len(ent_enemies(s2, 10))
                if d < 40 and (n != 1 or entity_counts[s2] < 4):
                    c *= 0.08
        if entity_counts[s2]:
            c *= 0.8
        if n_players != 2:
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
        return s.can_dock(p) and not p.is_full() and (get_owner_id(p) in (-1, my_id))

    def get_target_around(x):
        if type(x) == hlt.entity.Planet:
            if get_owner_id(x) in (-1, my_id):
                return x
            else:
                # return random.choice(x.all_docked_ships())
                # return iter(x.all_docked_ships()).__next__()
                return min(x.all_docked_ships(), 
                        key=lambda s: x.calculate_distance_between(s))
        else:
            return x

    def collided(x, y, r, t, ignore_list):
        for obs in all_entities:
            if obs in nav_targets:
                ox = obs.x + (nav_targets[obs][0] - obs.x) * t
                oy = obs.y + (nav_targets[obs][1] - obs.y) * t
            else:
                ox, oy = obs.x, obs.y
            if ((x-ox)**2+(y-oy)**2) <= (r+obs.radius)**2 \
                    and (obs.x,obs.y) not in ignore_list:
                return True
        return False

    def obstacles_between(pos1, pos2):
        vel_x = pos2[0] - pos1[0]
        vel_y = pos2[1] - pos1[1]
        
        for obs in all_entities:
            opos = (obs.x, obs.y)
            if opos == pos1 or pos_dist(pos1,opos) > 50:
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

    def closest_point(src, dst):
        theta = 0
        r = src.radius + dst.radius + 0.1
        travel_angle = math.atan2(src.y-dst.y, src.x-dst.x)
        idealX = dst.x + r * math.cos(travel_angle)
        idealY = dst.y + r * math.sin(travel_angle)
        phi = travel_angle + math.pi
        while theta < math.pi:
            x = idealX + r * (math.cos(phi) - math.cos(phi+theta))
            y = idealY + r * (math.sin(phi) - math.sin(phi+theta))
            if not collided(x, y, src.radius, 1, ((src.x,src.y),)):
                return hlt.entity.Position(x,y)
            # logging.info("theta = %.2f collided" % theta)
            theta += math.pi / 10 if theta >= 0 else 0
            theta = -theta
        return None

    def is_planet(e):
        return type(e) == hlt.entity.Planet
    def is_ship(e):
        return type(e) == hlt.entity.Ship

    # original_target is a (x,y) tuple
    def micro_policy(ship, original_target):
        near_friends = [s for s in live_ships if s!=ship and opt_dist(ship,s) <= 30]
        near_live_enemies = [s for s in live_enemy_ships if ent_dist(ship,s) <= 30]

        # if len(near_live_enemies) == 0 or len(near_friends) > len(near_live_enemies):
        #     return original_target

        def h(p):
            if n_players != 2:
                if ship_ratio < 1/3:
                    k_runaway = 1
                    k_target = 0.1
                    k_friends = -0.2
                else:
                    k_runaway = 1.2
                    k_target = 1
                    k_friends = 0.3
            else: # 2 players
                if game_state == MyState.EARLY:
                    smash = ship in should_gang_up or len(live_ships) > len(enemy_ships)
                    k_runaway = 0 if smash else 3
                    k_target = 1
                    k_friends = -0.2
                else:
                    k_runaway = 0.97 + random.random()*0.09
                    k_target = 1
                    # k_friends = math.exp((1 - ship_ratio) / 4)
                    k_friends = 0.3

            target_score = pos_dist(original_target, p) if original_target else 0
            target_score *= k_target

            if near_friends and k_friends:
                newp = lambda ss: nav_targets[ss] if ss in nav_targets else (ss.x,ss.y)
                friend_score = min(pos_dist(p,newp(ss)) for ss in near_friends) * k_friends
                # friend_score = sum(1 / (opt_dist(ship,ss)**2) for ss in near_friends) * k_friends
            else:
                friend_score = 0

            if len(near_friends) >= len(near_live_enemies) \
                    or (len(near_live_enemies) == 1
                        and ship.health > near_live_enemies[0].health
                        and len(ent_enemies(near_live_enemies[0], 7))):
                avoid_score = 0
            elif near_live_enemies and k_runaway:
                closest = min(near_live_enemies, key=lambda ss: pos_dist(p,(ss.x,ss.y)))
                avoid_pos = (closest.x, closest.y)
                avoid_score = pos_dist(avoid_pos, p) * k_runaway
                # if game_state == MyState.EARLY:
                #     closest_orig = min(near_live_enemies, key=lambda ss: ent_dist(ship, ss))
                #     if closest != closest_orig:
                #         avoid_score *= 0.85
                #     if min([p[0], p[1], game_map.width-p[0], game_map.height-p[1]]) < 5:
                #         avoid_score *= 0.8
            else:
                avoid_score = 0
            
            return avoid_score - target_score - friend_score


        thrusts = [2, 4, 6, 7] if game_state==MyState.NORMAL else [4,8,12,14]
        angles = [math.radians(a) for a in range(0,360,20)]
        pos1 = (ship.x, ship.y)
        best_pos = pos1
        best_sep = h(pos1)
        for t,a in itertools.product(thrusts, angles):
            pos2 = ship.x+t*math.cos(a), ship.y+t*math.sin(a)
            if not obstacles_between(pos1, pos2) \
                    and h(pos2) > best_sep \
                    and inbounds(pos2):
                best_pos = pos2
                best_sep = h(pos2)
        return best_pos if best_pos != pos1 else None


    ship_entity_combos = []
    for s in sorted(live_ships, key=lambda ss: ent_dist(nearest_planet(ss), ss)):
        be = best_entity(s)
        entity_counts[be] += 1
        if is_planet(be):
            pl_counts[be] += 1
        ship_entity_combos.append((be, s))

    # dock ships that can
    docking = set()
    docking_planets = collections.Counter()
    for best_entity, ship in ship_entity_combos:
        if is_planet(best_entity) \
                and can_dock(ship, best_entity) \
                and (len(ent_friendlies(ship, 20)) - docking_planets[best_entity]
                     >= len(ent_enemies(ship, 40))):
            if game_state == MyState.EARLY and (
                    ship in should_deal_with_attackers | should_avoid_attackers
                    or nearest_ship_dist(ship) < 40
            ):
                continue

            command_queue.append(ship.dock(best_entity))
            docking.add(ship)
            docking_planets[best_entity] += 1

    # for ship in sorted(live_ships, key=lambda s: s.calculate_distance_between(best_entity(s))):
    for i, (best_entity, ship) in enumerate(sorted(ship_entity_combos, 
                            key=lambda sec: sec[1].calculate_distance_between(sec[0]))):
        if time.time() - t_start > 1.3:
            break

        if ship not in docking:
            # checkpoint(str(i))

            # if n_players == 2 and ship.id == min(s.id for s in live_ships):
            #     if len(enemy_ships) == len(live_enemy_ships):
            #         greedy = min(enemy_ships, key=lambda s: ship.calculate_distance_between(s))
            #     else:
            #         greedy = min((s for s in enemy_ships if s.docking_status!=s.DockingStatus.UNDOCKED),
            #                           key=lambda s: ship.calculate_distance_between(s))

            if game_state == MyState.EARLY:
                if ship in should_deal_with_attackers:
                    if len(live_ships) <= 1:
                        # ts = [(1,1), (1,game_map.height-1), (game_map.width-1, 1), (game_map.width-1, game_map.height-1)]
                        # best_entity = max((hlt.entity.Entity(x,y,1,0,0,0) for x,y in ts), 
                        #                   key=lambda e: ent_dist(ship,e))
                        best_entity = hlt.entity.Entity(game_map.width/2,game_map.height/2,1,0,0,0)
                        # run away with no real goal
                    elif ship in should_gang_up:
                        best_entity = gang_up_target
                    else:
                        closest = min(live_ships+live_enemy_ships, key=lambda ss: ent_dist(ship,ss))
                        target_pool = live_enemy_ships if closest.owner.id == my_id else live_ships
                        if len(target_pool) == 1:
                            best_entity = target_pool[0]
                        else:
                            best_entity = sorted(target_pool, key=lambda ss: ent_dist(ship,ss))[1]
                        # if opt_dist(ship, best_entity) < 7:
                        #     dx = best_entity.x - ship.x
                        #     dy = best_entity.y - ship.y
                        #     best_entity = hlt.entity.Entity(ship.x-3*dx, ship.y-3*dy,1,0,0,0)
                
                elif ship in should_avoid_attackers: # avoid
                # else:
                    closest_enemy = min(live_enemy_ships, key=lambda ss: ent_dist(ship,ss))
                    farthest_pl = max(interested_planets, key=lambda ss: ent_dist(closest_enemy,ss))
                    if can_dock(ship, farthest_pl):
                        command_queue.append(ship.dock(farthest_pl))
                        docking.add(ship)
                        docking_planets[farthest_pl] += 1
                        continue
                    else:
                        best_entity = farthest_pl

            if is_planet(best_entity):
                if not planet_safe(best_entity, n_dock=docking_planets[best_entity]):
                    best_entity = min(
                        ent_enemies(best_entity, 40),
                        key=lambda s: best_entity.calculate_distance_between(s)
                    )

            target_entity = get_target_around(best_entity)

            if is_ship(best_entity) and ship.health < best_entity.health:
                navTarget = target_entity
            else:
                navTarget = closest_point(ship, target_entity)
            
            if navTarget:

                nextPos = micro_policy(ship, (navTarget.x, navTarget.y))
                if nextPos:
                    nx, ny = nextPos
                    mag = min(7, ((nx-ship.x)**2 + (ny-ship.y)**2)**0.5)
                    cmd = ship.thrust(round(mag), math.degrees(math.atan2(ny-ship.y, nx-ship.x))%360)
                    command_queue.append(cmd)
                    nav_targets[ship] = nextPos
                else:
                    o = min(set(game_map.all_planets()) | set(live_ships) - set((ship,)), 
                            key=lambda s: ship.calculate_distance_between(s))
                    angle = o.calculate_angle_between(ship)
                    step = 1.5
                    nx = ship.x + step * math.cos(math.radians(angle))
                    ny = ship.y + step * math.sin(math.radians(angle))
                    # logging.info("trying fallback planner")
                    if inbounds((nx,ny)) and not collided(nx, ny, 1.5, 1, [(ship.x,ship.y)]):
                        cmd = ship.thrust(step, angle)
                        command_queue.append(cmd)
                        nav_targets[ship] = (nx, ny)
                        # logging.info("used fallback planner")

    if len(command_queue) == 0:
        command_queue.append(game_map.get_me().all_ships()[0].thrust(0,0))

    # for ship in live_ships:
    #     if ship in nav_targets:
    #         p1 = ship.x, ship.y
    #         p2 = nav_targets[ship]
    #         assert not obstacles_between(p1, p2, ignore=(p1,))
    
    game.send_command_queue(command_queue)

