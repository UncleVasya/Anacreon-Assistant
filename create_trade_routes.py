import itertools
import json
import os

from lib.anacreonlib import anacreon
from lib.anacreonlib.anacreon import Anacreon


class SkipWorldException(Exception):
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


def counter(func):
    def wrapper(*args, **kwargs):
        # setattr(wrapper, 'count', getattr(wrapper, 'count', 0) + 1)
        wrapper.count = getattr(wrapper, 'count', 0) + 1
        return func(*args, **kwargs)
    return wrapper


def main():
    def what_world_needs(world: dict) -> set:
        # base needs
        base_needs = {x for x in world['baseConsumption'][::3]}
        print('\nBase consumption:', [api.scenario_info[x]['nameDesc'] for x in base_needs])

        # world industries needs
        resources_by_trait = [x['productionData'] for x in world['traits']
                              if type(x) is dict and 'productionData' in x.keys()]
        resources = list(itertools.chain(*resources_by_trait))  # flat list of resources data
        production_needs = {res for i, res in enumerate(resources[::3])
                            if resources[i*3+1] < 0}  # quantity produced flag, negative means consumed
        print('Production needs:', [api.scenario_info[x]['nameDesc'] for x in production_needs])

        # combined needs, ignoring life support goods
        return base_needs | production_needs - life_support_goods

    def what_world_offers(world: dict) -> set:
        primary_trait = next((x for x in world['traits'] if type(x) is dict and x.get('isPrimary', None)), {})
        build_data = primary_trait.get('buildData', [])
        primary_resources = {res for i, res in enumerate(build_data[::3])
                             if not build_data[i*3+2]  # cannotBuild flag
                             and api.scenario_info[res]['category'] == 'commodity'}  # filter out units
        return primary_resources

    def what_world_imports(world: dict, ignore_hubs=False) -> set:
        imports = set()
        for route in world.get('tradeRoutes', []):
            partner = api.get_obj_by_id(route['partnerObjID'])
            designation = api.scenario_info[partner['designation']]
            if ignore_hubs and designation['unid'] == 'core.tradingHubDesignation':
                continue

            if 'return' in route.keys():  # The data for this route belongs to another world
                route = next(r for r in partner['tradeRoutes'] if r['partnerObjID'] == world['id'])
                imports.update(route.get('exports', [])[::4])
            else:
                imports.update(route.get('imports', [])[::4])
        return imports

    def world_exporters_by_resource(world: dict, resource: int) -> list:
        exporters = []
        for route in world.get('tradeRoutes', []):
            if 'return' in route.keys():  # The data for this route belongs to another world
                partner = api.get_obj_by_id(route['partnerObjID'])
                route = next(r for r in partner['tradeRoutes'] if r['partnerObjID'] == world['id'])
                if resource in route.get('exports', [])[::4]:
                    exporters.append(partner['id'])
            else:
                if resource in route.get('imports', [])[::4]:
                    exporters.append(route['partnerObjID'])
        return [api.get_obj_by_id(x) for x in exporters]

    def is_route_present(world: dict, partner: dict, alloc_type: str, alloc_value: float = None,
                         res_type: int = None) -> bool:
        try:
            route = next((x for x in world['tradeRoutes'] if x['partnerObjID'] == partner['id']))
            if 'return' in route.keys():  # The data for this route belongs to another world
                route = next(r for r in partner['tradeRoutes'] if r['partnerObjID'] == world['id'])
                alloc_type = 'exports' if alloc_type == 'imports' else 'imports' if alloc_type == 'exports' else alloc_type
                # TODO: alloc_type = 'exportTech' if alloc_type = 'importTech'
            data = route[alloc_type]
            for i, resource in enumerate(data[::4]):
                if resource == res_type and int(data[i*4+1]) == alloc_value:
                    return True
        except (KeyError, StopIteration):
            pass  # there is no route between these worlds
        return False

    # def should_create_import_route(world: dict, partner: dict, alloc_value: float = None,
    #                                res_type: int = None) -> bool:
    #     return can_export(partner, res_type) and not is_route_present(world, partner, )

    def in_trade_range(world: dict, objects: list) -> list:
        pass

    def is_in_admin_range(world: dict) -> bool:
        if not caps:
            return False

        admin_range = 250
        capitals = sorted(caps, key=lambda x: api.dist(x['pos'], world['pos']))
        print('\nCapitals distance:')
        for cap in capitals:
            print('%s: %.2f' % (cap['name'], api.dist(cap['pos'], world['pos'])))

        cap = capitals[0]
        print('\nClosest capital:', cap['name'])

        caps_in_range = [x for x in capitals if api.dist(x['pos'], world['pos']) <= admin_range]
        print('\nCaps in range: %s' % [x['name'] for x in caps_in_range])
        if caps_in_range:
            print('%s belongs to cap %s (distance %.2f)' %
                  (world['name'], cap['name'], api.dist(cap['pos'], world['pos'])))
        return bool(caps_in_range)  # true if list isn't empty

    print(os.environ.get('PYTHONPATH'))
    print(os.environ.get("LOGIN"), os.environ.get("PASSWORD"))
    # TODO: use ANACREON_LOGIN and ANACREON_PASSWORD names to avoid possible conflicts
    api = Anacreon(os.environ.get("LOGIN"), os.environ.get("PASSWORD"))

    # set decorator to count requests
    api.set_trade_route = counter(api.set_trade_route)
    api.stop_trade_route = counter(api.stop_trade_route)

    api.gameID = os.environ.get("GAME_ID")

    gameList = api.get_game_list()
    gameInfo = api.get_game_info()
    api.sovID = gameInfo['userInfo']['sovereignID']
    gameObjects = api.get_objects()

    my_worlds = [x for x in api.objects_dict.values()
                 if x['sovereignID'] == api.sovID and x['class'] == 'world']
    hubs = [x for x in my_worlds if api.scenario_info[x['designation']]['unid'] == 'core.tradingHubDesignation']
    fonds = [x for x in my_worlds if api.scenario_info[x['designation']]['unid'] == 'core.universityDesignation']
    caps = [x for x in my_worlds
            if api.scenario_info[x['designation']].get('role', None) in ('sectorCapital', 'imperialCapital')
            and 'buildComplete' not in x]  # not having a buildComplete date means thing is already built

    life_support_goods = {
        next(x['id'] for x in api.scenario_info.values() if x.get('unid') == 'core.airFilters'),
        next(x['id'] for x in api.scenario_info.values() if x.get('unid') == 'core.radiationMeds'),
        next(x['id'] for x in api.scenario_info.values() if x.get('unid') == 'core.radiationShielding'),
        next(x['id'] for x in api.scenario_info.values() if x.get('unid') == 'core.lifeSupportSupplies'),
    }

    correct_routes = set()

    print('\nMy worlds: %s' % len(my_worlds))
    print("\nHubs: %s" % [x['name'] for x in hubs])
    print("Foundations: %s" % [x['name'] for x in fonds])
    print("Capitals: %s" % [x['name'] for x in caps])
    print('\n')
    # world = my_worlds[0]

    # calc initial imports for hubs
    for hub in hubs:
        hub['can_export'] = what_world_imports(hub, ignore_hubs=True)  # everything that we get from producer worlds

    for world in my_worlds:
        try:
            print('\nWorld:', world['name'])

            designation = api.scenario_info[world['designation']]
            print('Designation:', designation['nameDesc'])
            print('Tech:', world['techLevel'])

            # determine max trade distance
            # TODO: game client uses this to check for spaceport:
            #       importerHasSpaceport = (this.tradeRouteMax != null && this.tradeRouteMax > 0)
            traits = [(x if type(x) is int else x['traitID']) for x in world['traits']]  # flat list of ids
            has_spaceport = any(api.scenario_info[x].get('role', None) == 'spaceport' for x in traits)
            trade_distance = 200 if has_spaceport else 100
            print('Trade distance:', trade_distance, '(no spaceport)' if not has_spaceport else '')

            if not is_in_admin_range(world):
                print('%s is not in admin range.' % world['name'])
                raise SkipWorldException()

            if not hubs:
                continue

            # if this world is not a hub, create trade route with closest hub
            # TODO: closest hub that has needed resource
            if designation['unid'] != 'core.tradingHubDesignation':
                # TODO: in_range should be a func that I can use for fonds too
                print('\nTrade hubs distance:')
                hubs.sort(key=lambda x: api.dist(x['pos'], world['pos']))
                for hub in hubs:
                    print('%s: %.2f' % (hub['name'], api.dist(hub['pos'], world['pos'])))

                hub = hubs[0]  # closest hub
                print('\nClosest hub: %s  (distance %.2f)' % (hub['name'], api.dist(hub['pos'], world['pos'])))

                hubs_in_range = [x for x in hubs if api.dist(x['pos'], world['pos']) <= trade_distance]
                print('\nHubs in range: %s' % [x['name'] for x in hubs_in_range])

                if hubs_in_range:
                    # hub = min(hubs_in_range, key=lambda x: api.dist(x['pos'], world['pos']))

                    print('%s belongs to hub %s (distance %.2f)' %
                          (world['name'], hub['name'], api.dist(hub['pos'], world['pos'])))

                    for_export = what_world_offers(world)
                    print('\nCan export:', [api.scenario_info[x]['nameDesc'] for x in for_export])

                    for_import = what_world_needs(world)
                    print('\nShould import:', [api.scenario_info[x]['nameDesc'] for x in for_import])

                    hub_offers = hub['can_export']
                    print('\n%s offers: %s' % (hub['name'], [api.scenario_info[x]['nameDesc'] for x in hub_offers]))

                    for_import = for_import & hub_offers
                    print('\nCan import:', [api.scenario_info[x]['nameDesc'] for x in for_import])

                    # TODO: look for a closes hub that has everything world needs. If no hub in range has everything,
                    #       then create multiple import routes

                    correct_routes.add(frozenset({world['id'], hub['id']}))

                    print('\nSetting trade routes:')
                    # imports
                    print('%s -> %s: all demand  ' % (hub['name'], world['name']), end='', flush=True)
                    if not all([is_route_present(world, hub, 'imports', 100, x) for x in for_import]):
                        # TODO: if DefaultRoute brings issues, replace it with explicit routes
                        #       (issues will arise if I want to import resources from both hub and another planet)
                        api.set_trade_route(world['id'], hub['id'], 'addDefaultRoute')
                        print('[added]')
                    else:
                        print('[present]')

                    # exports
                    for resource in for_export:
                        print('%s -> %s: %s  ' % (world['name'], hub['name'], api.scenario_info[resource]['nameDesc']),
                              end='', flush=True)
                        amount = 100
                        if not is_route_present(world, hub, 'exports', amount, resource):
                            api.set_trade_route(hub['id'], world['id'], 'consumption', amount, resource)
                            print('[added]')
                        else:
                            print('[present]')

                    # now create special resource propagation routes to other hubs
                    # (hubs can operate only on resources that they import;
                    #  importing 0% is enough to let hub know it can export this resource)
                    hubs_in_range = [x for x in hubs_in_range if x != hub]  # remove our parent hub
                    if hubs_in_range:
                        print('\n---Propagation routes---')
                    for resource in for_export:
                        for hub in hubs_in_range:
                            exporters = world_exporters_by_resource(hub, resource)
                            # we count only producer planets here, not other hubs
                            exporters = [x for x in exporters
                                         if api.scenario_info[x['designation']]['unid'] != 'core.tradingHubDesignation']

                            print('\n%s %s exporters: %s' % (hub['name'], api.scenario_info[resource]['nameDesc'],
                                  [x['name'] for x in exporters]))
                            print('\n%s -> %s: %s  ' % (
                                  world['name'], hub['name'], api.scenario_info[resource]['nameDesc']),
                                  end='', flush=True)

                            print('\n%s can export: %s' %
                                  (hub['name'], [api.scenario_info[x]['nameDesc'] for x in hub['can_export']]))

                            if not exporters and resource not in hub['can_export']:  # also checks for newly added imports
                                api.set_trade_route(hub['id'], world['id'], 'consumption', 0, resource)
                                correct_routes.add(frozenset({world['id'], hub['id']}))
                                hub['can_export'].add(resource)
                                print('[added]')
                            elif len(exporters) == 1 and exporters[0]['id'] == world['id']:
                                correct_routes.add(frozenset({world['id'], hub['id']}))
                                if not is_route_present(world, hub, 'exports', 0, resource):
                                    api.set_trade_route(hub['id'], world['id'], 'consumption', 0, resource)
                                    print('[fixed]')
                                else:
                                    print('[present]')
                            else:
                                print('[not needed]')

            # if this world is not a fond, create tech route with closest fond
            if designation['unid'] != 'core.universityDesignation':
                print('\nFoundations distance:')
                fonds.sort(key=lambda x: api.dist(x['pos'], world['pos']))
                for fond in fonds:
                    print('%s: %.2f' % (fond['name'], api.dist(fond['pos'], world['pos'])))

                fonds_in_range = [x for x in fonds if api.dist(x['pos'], world['pos']) <= trade_distance]
                print('\nFoundations in range: %s' % [x['name'] for x in fonds_in_range])

                if fonds_in_range:  # if we have fonds in range
                    # fond = min(fonds_in_range, key=lambda x: api.dist(x['pos'], world['pos']))
                    fond = fonds_in_range[0]  # closest fond
                    print('%s belongs to fond %s (distance %.2f)' %
                          (world['name'], fond['name'], api.dist(fond['pos'], world['pos'])))

                    print('\nSetting tech route:')
                    level = fond['techLevel']
                    print('%s -> %s: %s' % (fond['name'], world['name'], level), end='', flush=True)
                    if not is_route_present(world, fond, 'importTech', level):
                        api.set_trade_route(world['id'], fond['id'], 'tech', level)
                        correct_routes.add(frozenset({world['id'], fond['id']}))
                        print('  [added]')
                    else:
                        print('  [present]')

        except (anacreon.HexArcException, SkipWorldException) as e:
            if isinstance(e, anacreon.HexArcException):
                print('\nGot exception: \n%s\n%s\n' % (e.__class__, e))
            print('\nSkipping this world.')
        finally:
            print('\nsetTradeRoute requests: %d total (limit: 120/hr)' % getattr(api.set_trade_route, 'count', 0))
            print('\n---------\n')

    # mark routes between hubs as correct, they are manually managed by player
    print('\nMarking routes between hubs as correct')
    for hub in hubs:
        for route in hub.get('tradeRoutes', []):
            partner = api.get_obj_by_id(route['partnerObjID'])
            if api.scenario_info[partner['designation']]['unid'] == 'core.tradingHubDesignation':
                correct_routes.add(frozenset({hub['id'], partner['id']}))
                print('%s <-> %s' % (hub['name'], partner['name']))

    # remove all trade routes that aren't marked as correct
    print('\nClearing obsolete trade routes\n')
    for world in my_worlds:
        for route in world.get('tradeRoutes', []):
            if 'return' in route.keys():
                continue  # don't need to clean one route two times

            partner = api.get_obj_by_id(route['partnerObjID'])
            if frozenset({world['id'], partner['id']}) not in correct_routes:
                # remember tech part of the route, if present
                # (for a case when route has both trade and tech exports, usually between hub and fond)
                exportTech = route.get('exportTech', None)
                importTech = route.get('importTech', None)

                print('%s <-> %s: clearing' % (world['name'], partner['name']))
                api.stop_trade_route(world['id'], partner['id'])

                if {'imports', 'exports'}.isdisjoint(route.keys()):
                    continue  # this is a tech-only route, no need to preserve anything

                # recreate tech part of the route
                if exportTech:
                    api.set_trade_route(partner['id'], world['id'], exportTech[0])
                    print('%s -> %s: uplift to %d recreated' % (world['name'], partner['name'], exportTech[0]))
                elif importTech:
                    api.set_trade_route(world['id'], partner['id'], importTech[0])
                    print('%s -> %s: uplift to %d recreated' % (partner['name'], world['name'], importTech[0]))

    print('\nstopTradeRoute requests: %d total (limit: 120/hr\n)' % getattr(api.stop_trade_route, 'count', 0))


if __name__ == '__main__':
    main()

