
import hlt
import logging

game = hlt.Game("EB1")

# logging.info("Starting MyBot1")

while True:
    game_map = game.update_map()
    command_queue = []

    live_ships = [x for x in game_map.get_me().all_ships() if x.docking_status == x.DockingStatus.UNDOCKED]
    # logging.info(live_ships)
    for p in game_map.all_planets():
        logging.info(p.owner.id if p.owner else None)

    get_owner_id = lambda pl: pl.owner.id if pl.owner else -1

    owned = [x for x in game_map.all_planets() if get_owner_id(x) == game_map.my_id]
    if len(owned) == 0:
        owned += live_ships
    unowned = [x for x in game_map.all_planets() if get_owner_id(x) != game_map.my_id]
    
    pl_cost_fn = lambda pl: sum(x.calculate_distance_between(pl) for x in owned)
    
    target_planet = min(unowned, key=pl_cost_fn)
    
    arrived = [x for x in live_ships if x.can_dock(target_planet)]
    unarrived = [x for x in live_ships if not x.can_dock(target_planet)]
    n_dock = min(len(arrived), 
                 target_planet.num_docking_spots - len(target_planet.all_docked_ships()))

    for ship in arrived[:n_dock]:
        command_queue.append(ship.dock(target_planet))

    if get_owner_id(target_planet) == -1:
        target = target_planet
    else:
        target = iter(target_planet.all_docked_ships()).__next__()

    for ship in unarrived + arrived[n_dock:]:
        cmd = ship.navigate(
            ship.closest_point_to(target), 
            game_map, 
            speed=hlt.constants.MAX_SPEED*0.8, 
            ignore_ships=False
        )
        if cmd: command_queue.append(cmd)

    game.send_command_queue(command_queue)
