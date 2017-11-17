import hlt
import logging
import time
import random

game = hlt.Game("EB4")

# n = max(1, game.map.width // 100 - len(game.map.all_players()))
# if len(game.map.all_players()) == 2:
#     n = 2
# else:
#     n = 1
# n = 2

# logging.info("N = %d" % n)

while True:
    t_start = time.time()
    game_map = game.update_map()
    command_queue = []

    live_ships = [x for x in game_map.get_me().all_ships() if x.docking_status == x.DockingStatus.UNDOCKED]
    # random.shuffle(live_ships)
    # logging.info(live_ships)
    # for p in game_map.all_planets():
        # logging.info(p.owner.id if p.owner else None)

    get_owner_id = lambda pl: pl.owner.id if pl.owner else -1

    owned = [x for x in game_map.all_planets() if get_owner_id(x) == game_map.my_id]
    nonfull = [x for x in owned if not x.is_full()]
    if len(owned) == 0:
        owned += live_ships
    unowned = [x for x in game_map.all_planets() if get_owner_id(x) != game_map.my_id]
    if len(unowned) == 0:
        game.send_command_queue([])
        continue
    
    # def pl_cost_fn(pl):
    #     dist_sum = sum(x.calculate_distance_between(pl) for x in owned)
    #     # ships_near = sum(1 if s.owner != game_map.my_id and s.can_dock(pl) else 0 for s in game_map._all_ships())
    #     # ships_docked = len(pl.all_docked_ships())
    #     return dist_sum / pl.num_docking_spots
    
    # target_planets = sorted(unowned + nonfull, key=pl_cost_fn)[:n]
    
    def ship_planet_cost(s, p):
        return s.calculate_distance_between(p) / p.num_docking_spots
    
    def nearest_planet(s):
        return min(unowned+nonfull, key=lambda p: s.calculate_distance_between(p))
    def best_planet(s):
        return min(unowned+nonfull, key=lambda p: ship_planet_cost(s,p))
    
    arrived = [x for x in live_ships if x.can_dock(best_planet(x))]
    unarrived = [x for x in live_ships if not x.can_dock(best_planet(x))]
    # n_dock = min(len(arrived), target_planet.num_docking_spots - len(target_planet.all_docked_ships()))

    arrived_leftover = []
    for ship in arrived:
        tpl = nearest_planet(ship)
        if tpl.is_full():
            arrived_leftover.append(ship)
        else:
            command_queue.append(ship.dock(tpl))

    def get_target_around_planet(tpl):
        if get_owner_id(tpl) in (-1, game_map.my_id):
            return tpl
        else:
            return iter(tpl.all_docked_ships()).__next__()

    # logging.info(time.time() - t_start)

    # i = 0
    for ship in sorted(unarrived+arrived_leftover, key=lambda s: s.calculate_distance_between(best_planet(s))):
        cmd = None
        
        # i+=1
        if time.time() - t_start < 1.25:
            # print(time.time() - t_start)
            # nt = nearest_target(ship)
            # tap = get_target_around_planet(nt)
            # logging.info("%d\n    %s\n    %s" % (i, str(nt), str(tap)))
            cmd = ship.navigate(
                ship.closest_point_to(get_target_around_planet(best_planet(ship))), 
                game_map, 
                speed=hlt.constants.MAX_SPEED, 
                ignore_ships=False,
                max_corrections=100
            )
            # logging.info(cmd)
        if cmd:
            command_queue.append(cmd)

    if len(command_queue) == 0 and len(live_ships) > 0:
        command_queue.append(live_ships[0].thrust(0,0))
    game.send_command_queue(command_queue)
