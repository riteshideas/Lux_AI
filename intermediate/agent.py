from itertools import count
import math, sys
from shutil import move
from lux.game import Game
from lux.game_map import Cell, RESOURCE_TYPES
from lux.constants import Constants
from lux.game_constants import GAME_CONSTANTS
from lux import annotate
import random

DIRECTIONS = Constants.DIRECTIONS

game_state = None
build_loc = None

unit_to_resource_dict = {}
unit_to_city = {}
unit_actions = {}

global_observation = 0



with open("../agent.log", "w") as f:
    f.write("")

def log(text):
    global global_observation

    with open("../agent.log", "a") as f:
        f.write(f"[{global_observation['step']}] : {text}\n")

def get_resource_tiles(game_state, width, height):
    returnLst: list[Cell] = []
    for y in range(height):
        for x in range(width):
            cell = game_state.map.get_cell(x, y)
            if cell.has_resource():
                returnLst.append(cell)
    return returnLst

def get_closest_resource_tile(unit, resource_tiles, player):
    # if the unit is a worker and we have space in cargo, lets find the nearest resource tile and try to mine it
    closest_dist = math.inf
    closest_resource_tile = None

    for resource_tile in resource_tiles:
        if resource_tile.resource.type == Constants.RESOURCE_TYPES.COAL and not player.researched_coal(): continue
        if resource_tile.resource.type == Constants.RESOURCE_TYPES.URANIUM and not player.researched_uranium(): continue
        dist = resource_tile.pos.distance_to(unit.pos)
        if dist < closest_dist:
            closest_dist = dist
            closest_resource_tile = resource_tile

    return closest_resource_tile

def get_close_city_tile(player, unit):
    closest_dist = math.inf
    closest_city_tile = None
    for k, city in player.cities.items():
        for city_tile in city.citytiles:
            if city_tile not in unit_to_city:
                dist = city_tile.pos.distance_to(unit.pos)
                if dist < closest_dist:
                    closest_dist = dist
                    closest_city_tile = city_tile

    return closest_city_tile

def return_removed_list(lst, remove_item):
    lst.remove(remove_item)
    return lst

def find_empty_tile_near(game_state, empty_tile):
    build_loc = None
    dirs = [(0,1), (1, 0), (0, -1), (-1, 0)]
    for d in dirs:
        try:
            possible_empty_tile = game_state.map.get_cell(empty_tile.pos.x + d[0], empty_tile.pos.y + d[1])
            if possible_empty_tile.resource == None and possible_empty_tile.road == 0 and possible_empty_tile.citytile == None:
                build_loc = possible_empty_tile
                log(f"Build pos : {build_loc.pos}")
                break
    
        except Exception as e:
            log(f"Error : {str(e)}")
    return build_loc
    

def agent(observation, configuration):
    global game_state
    global build_loc
    global unit_to_resource_dict
    global unit_to_city
    global global_observation
    global unit_actions

    ### Do not edit ###
    if observation["step"] == 0:
        game_state = Game()
        game_state._initialize(observation["updates"])
        game_state._update(observation["updates"][2:])
        game_state.id = observation.player
    else:
        game_state._update(observation["updates"])
    
    actions = []
    global_observation = observation
    ### AI Code goes down here! ### 
    player = game_state.players[observation.player]
    opponent = game_state.players[(observation.player + 1) % 2]
    width, height = game_state.map.width, game_state.map.height



    workers = [x for x in player.units if x.is_worker()]
    cities = player.cities.values()
    city_tiles = []

    for city in cities:
        for c_tile in city.citytiles:
            city_tiles.append(c_tile)


    resource_tiles: list[Cell] = get_resource_tiles(game_state, width, height)

    for w in workers:
        if w not in unit_to_resource_dict:
            unit_to_resource_dict[w.id] = get_closest_resource_tile(w, resource_tiles, player)

    for w in workers:
        if w.id not in unit_to_city:
            unit_to_city[w.id] = get_close_city_tile(player, w)


    build_city = False
    if (len(workers) + 0.1) / (len(city_tiles) + 0.1) >= 0.8: # The 0.1 to avoid zero division error but still obtain accuracy
        build_city = True


    for i in city_tiles:
        if len(city_tiles) > len(player.units):
            action = i.build_worker()
            actions.append(action)


    # We iterate over all our units and do something with them
    for unit in player.units:
        if unit.is_worker() and unit.can_act():

            # if the unit is a worker and we have space in cargo, lets find the nearest resource tile and try to mine it
            if unit.get_cargo_space_left() > 0:

                # Getting all the resource tiles that are not taken but other units
                unit_move_dir  = None
                possible_resource_tile = unit_to_resource_dict[unit.id]
                cell = game_state.map.get_cell_by_pos(possible_resource_tile.pos)


                if cell.has_resource():
                    unit_move_dir = unit.pos.direction_to(cell.pos)
                else:
                    possible_resource_tile = get_closest_resource_tile(unit, resource_tiles, player)
                    unit_to_resource_dict[unit.id] = possible_resource_tile
                    unit_move_dir = unit.pos.direction_to(possible_resource_tile.pos)
                    log(f"Worker, {unit.id} had no available resources, redirected him to {unit_to_resource_dict[unit.id].pos}")

                if (unit.pos, unit_move_dir) in unit_actions.values() and unit.id in unit_actions and unit_actions[unit.id] != (unit.pos, unit_move_dir):
                    actions.append(random.choice(return_removed_list(["n", "s", "e", "w", "c"], unit_move_dir)))
                    continue
                else:
                    actions.append(unit.move(unit_move_dir))
                    unit_actions[unit.id] = (unit.pos, unit_move_dir)

            else:

                if build_city:
                    log("We want to build city!")
                    if build_loc is None:

                        empty_tile = get_close_city_tile(player, unit)
                        build_loc = find_empty_tile_near(game_state, empty_tile)

                    if build_loc is not None and unit.pos == build_loc.pos:
                        log("Building city, Yay!")
                        action = unit.build_city()
                        actions.append(action)

                        build_city = False
                        build_loc = None
                        continue

                    elif build_loc != None:
                        log(f"Going to build city : {build_loc.pos}")
                        next_tile_pos = unit.pos.translate(unit.pos.direction_to(build_loc.pos), len(player.units))
                        next_move_dir = unit.pos.direction_to(build_loc.pos)
                        next_tile = game_state.map.get_cell(next_tile_pos.x, next_tile_pos.y)

                        log(f"Next tile : {next_tile.pos}  {unit.id}")

                        if (next_tile.citytile != None):
                            if next_move_dir  == "n" or next_move_dir == "s":
                                move_dir = random.choice(["e", "w"])

                            elif next_move_dir  == "e" or next_move_dir == "w":
                                move_dir = random.choice(["n", "s"])
                        else:
                            move_dir = unit.pos.direction_to(build_loc.pos)

                        if (unit.pos, move_dir) in unit_actions.values() and unit.id in unit_actions and unit_actions[unit.id] != (unit.pos, move_dir):
                            actions.append(random.choice(return_removed_list(["n", "s", "e", "w", "c"], move_dir)))
                        else:
                            actions.append(unit.move(move_dir))
                            unit_actions[unit.id] = (unit.pos, move_dir)


                # if unit is a worker and there is no cargo space left, and we have cities, lets return to them
                elif len(player.cities) > 0:
                    if unit.id in unit_to_city and unit_to_city[unit.id] in city_tiles:
                        actions.append(unit.move(unit.pos.direction_to(unit_to_city[unit.id].pos)))
                    else:
                        unit_to_city[unit.id] = get_close_city_tile(player, unit)
                        actions.append(unit.move(unit.pos.direction_to(unit_to_city[unit.id].pos)))
    log(unit_actions)
    # you can add debug annotations using the functions in the annotate object
    # actions.append(annotate.circle(0, 0))
    return actions
