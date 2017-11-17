import hlt
import logging
import time
import random
from itertools import chain

game = hlt.Game("EB3")

# logging.info("Starting MyBot1")

while True:
    game_map = game.update_map()
    command_queue = []
    t_start = time.time()

    live_ships = [x for x in game_map.get_me().all_ships() if x.docking_status == x.DockingStatus.UNDOCKED]
    random.shuffle(live_ships)
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
    
    pl_cost_fn = lambda pl: sum(x.calculate_distance_between(pl) for x in owned)
    
    target_planet = min(unowned + nonfull, key=pl_cost_fn)
    
    arrived = [x for x in live_ships if x.can_dock(target_planet)]
    unarrived = [x for x in live_ships if not x.can_dock(target_planet)]
    n_dock = min(len(arrived), 
                 target_planet.num_docking_spots - len(target_planet.all_docked_ships()))

    for ship in arrived[:n_dock]:
        command_queue.append(ship.dock(target_planet))

    if get_owner_id(target_planet) in (-1, game_map.my_id):
        target = target_planet
    else:
        target = iter(target_planet.all_docked_ships()).__next__()

    # logging.info(time.time() - t_start)

    # i = 0
    for ship in sorted(unarrived+arrived[n_dock:], key=lambda s: s.calculate_distance_between(target)):
        cmd = None
        if time.time() - t_start < 1.2:
            # print(time.time() - t_start)
            cmd = ship.navigate(
                ship.closest_point_to(target), 
                game_map, 
                speed=hlt.constants.MAX_SPEED, 
                ignore_ships=False,
                max_corrections=100
            )
        if cmd:
            command_queue.append(cmd)

    if len(command_queue) == 0 and len(live_ships) > 0:
        command_queue.append(live_ships[0].thrust(0,0))
    game.send_command_queue(command_queue)
