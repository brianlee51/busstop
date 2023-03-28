from django.shortcuts import render, redirect
from django.conf import settings
import csv
import math
import folium
import os
import requests
import polyline


# TODO: Make start position a red marker, and end position a green marker [OK]
# TODO: Use an API to show the curvature of the route between points [OK]
# TODO: Solve the "opposite" bus stop problem (nearest bus stops around you)
# TODO: where to change buses [OK]
# TODO: Have a front end to allow user to set start point and end point? [OK]
# TODO: "straight line" distance calcuation is not the same as "road distance"
# TODO: If there's time make the front end better

# Create your views here.

# global csv file reader handler
csv_path = os.path.join(settings.BASE_DIR, 'scheduling', 'bus_stop.csv')
stops_csv = open(csv_path, 'r')
reader = csv.DictReader(stops_csv)

bus_stop_name_position_dict = {}

route_lookup_dict = {}

for row in reader:
    stop_name = row['name']
    stop_id = row['stop_id']
    route = row['route']
    stop_lon, stop_lat = row['longlat'].split(',')
    bus_stop_name_position_dict[stop_name] = (float(stop_lat), float(stop_lon))
    if stop_name in route_lookup_dict.keys():
        route_lookup_dict[stop_name].append({'stop_id': stop_id, 'route': route})
    else:
        route_lookup_dict[stop_name] = [{'stop_id': stop_id, 'route': route}]

def home(request):
    if request.method == 'GET':
        return render(request, 'index.html')

def route(request):
    start_walking = request.GET.get("start_position")
    end_walking = request.GET.get("end_position")
    print(':::: start position: ', start_walking, '::::')
    print(':::: end position: ', end_walking, '::::')
    # define the start and end locations in latlng
    start_lon, start_lat = start_walking.split(',')
    end_lon, end_lat = end_walking.split(',')

    start_lat = start_lat.strip(' ')
    start_lon = start_lon.strip(' ')
    end_lat = end_lat.strip(' ')
    end_lon = end_lon.strip(' ')

    print('start_lat: ', start_lat)
    print('start_lon: ', start_lon)
    print('end_lat: ', end_lat)
    print('end_lon: ', end_lon)

    #  find 5 closest bus stop nearest to the person
    nearest_starting_bus_stops = nearest_bus_stops(float(start_lon), float(start_lat), 5)
    closest_starting_stop = nearest_starting_bus_stops[0]
    closest_starting_bus_stop_name = closest_starting_stop[1]
    # have to find the lat, long of the closest stop
    start_stop_lat, start_stop_lon = bus_stop_name_position_dict.get(closest_starting_bus_stop_name)

    print(start_stop_lat, start_stop_lon)
    # ::::::::::::::::::::::::::::: OSRM ::::::::::::::::::::::::::::::
    url = f'https://router.project-osrm.org/route/v1/walking/{start_lat},{start_lon};{start_stop_lat},{start_stop_lon}?overview=full'
    response = requests.get(url)

    if response.status_code == 200:
        route = response.json()['routes'][0]
        distance = route['distance']  # in meters
        duration = route['duration']  # in seconds
        geometry = route['geometry']  # polyline string
        starting_decoded_polyline = polyline.decode(geometry)
    else:
        print('Error:', response.reason, response.content)


    #  find 5 closest bus stop nearest to the end place
    nearest_ending_bus_stops = nearest_bus_stops(float(end_lon), float(end_lat), 5)
    closest_ending_stop = nearest_ending_bus_stops[0]
    closest_ending_bus_stop_name = closest_ending_stop[1]
    # have to find the lat, long of the closest stop
    ending_stop_lat, ending_stop_lon = bus_stop_name_position_dict.get(closest_ending_bus_stop_name)

    #  print(ending_stop_lat, ending_stop_lon)
    # ::::::::::::::::::::::::::::: OSRM ::::::::::::::::::::::::::::::
    url = f'https://router.project-osrm.org/route/v1/walking/{end_lat},{end_lon};{ending_stop_lat},{ending_stop_lon}?overview=full'
    response = requests.get(url)

    if response.status_code == 200:
        route = response.json()['routes'][0]
        distance = route['distance']  # in meters
        duration = route['duration']  # in seconds
        geometry = route['geometry']  # polyline string
        ending_decoded_polyline = polyline.decode(geometry)
    else:
        print('Error:', response.reason, response.content)

    # ::::::::::::::::::::::::::::: END OSRM :::::::::::::::::::::::::
    unique_stops = {}
    locations = []

    routes = {
        'P101-LOOP': [],
        'P102-01': [],
        'P102-02': [],
        'P106-LOOP': [],
        'P202-LOOP': [],
        'P211-01': [],
        'P211-02': [],
        'P411-01': [],
        'P411-02': [],
        'P403-LOOP': [],
    }
    route_colours = {
        'P101-LOOP': 'red',
        'P102-01': 'blue',
        'P102-02': 'gray',
        'P106-LOOP': 'orange',
        'P202-LOOP': 'green',
        'P211-01': 'purple',
        'P211-02': 'pink',
        'P411-01': 'lightblue',
        'P411-02': 'lightgray',
        'P403-LOOP': 'black',
    }

    all_route_names = routes.keys()

    g = Graph()
    csv_path = os.path.join(settings.BASE_DIR, 'scheduling', 'bus_stop.csv')
    stops_csv = open(csv_path, 'r')
    reader = csv.DictReader(stops_csv)

    for row in reader:
        route = row['route']
        stop_id = row['stop_id']
        stop_name = row['name']
        long, lat = row['longlat'].split(',')
        #  print(route, stop_id, stop_name, long, lat)
        routes[route].append((stop_id, stop_name, float(long), float(lat)))

        # only add new stop
        if not unique_stops.get(stop_name):
            unique_stops[stop_name]  = (float(long), float(lat))
            g.add_node(stop_name)
        # to add stops and distances between

    for name in all_route_names:
        for stop in range(len(routes.get(name))-1):
            stop1 = routes.get(name)[stop]
            stop2 = routes.get(name)[stop+1]
            g.add_edge(
                stop1[1],
                stop2[1],
                haversine(stop1[3], stop1[2], stop2[3], stop2[2])
            )
    #  Dijkstra's routing
    shortest_path = g.shortest_path(closest_starting_bus_stop_name, closest_ending_bus_stop_name)

    for p in shortest_path:
        locations.append((p, float(unique_stops.get(p)[0]), float(unique_stops.get(p)[1])))
        #  print(p, 'long:', unique_stops.get(p)[0], 'lat:', unique_stops.get(p)[1])


    #  :::::::: OSRM API FOR CURVATURE OF ROUTE ::::::::
    to_encode = [bus_stop_name_position_dict.get(p) for p in shortest_path]
    journey_polyline = [(long, lat) for lat, long in to_encode]
    journey_polyline_points_encode = polyline.encode(journey_polyline)
    url = f'https://router.project-osrm.org/route/v1/driving/polyline({journey_polyline_points_encode})?overview=full'
    response = requests.get(url)

    if response.status_code == 200:
        route = response.json()['routes'][0]
        distance = route['distance']  # in meters
        duration = route['duration']  # in seconds
        geometry = route['geometry']  # polyline string
        journey_polyline_decode = polyline.decode(geometry)
    else:
        print('Error:', response.reason, response.content)

    #  :::::::: OSRM API FOR CURVATURE OF ROUTE ::::::::
        
    m = folium.Map(location=[start_lon, start_lat],zoom_start=18)

    #  :::::::: Draw Polylines ::::::::
    folium.PolyLine(
        locations=starting_decoded_polyline,
        color='red',
        weight=5
    ).add_to(m)

    folium.PolyLine(
        locations=journey_polyline_decode,
        color='blue',
        weight=5
    ).add_to(m)
    
    folium.PolyLine(
        locations=ending_decoded_polyline,
        color='green',
        weight=5
    ).add_to(m)


    # :::::::: Draw marker points ::::::::
    folium.Marker(
        location=[start_lon, start_lat],
        icon=folium.Icon(color='red')
    ).add_to(m)

    folium.Marker(
        location=[end_lon, end_lat],
        icon=folium.Icon(color='green')
    ).add_to(m)

    #  plot the dijkstra's routing
    # set starting bus stop point to red marker
    start_journey_point = locations[0]
    folium.Marker(
        location=[start_journey_point[1], start_journey_point[2]],
        popup= "{0}-{1}".format(1, start_journey_point[0]),
        icon=folium.Icon(color='red')
    ).add_to(m)

    # set ending bus stop point to green marker
    end_journey_point = locations[-1]
    folium.Marker(
        location=[end_journey_point[1], end_journey_point[2]],
        popup= "{0}-{1}".format(len(locations), end_journey_point[0]),
        icon=folium.Icon(color='green')
    ).add_to(m)

    #  routes with the most stops get the highest priority
    bus_priority = {}
    bus_priority_list = []
    routing_queue = []
    route_names = []
    all_routes_available = []
    for loc in locations:
        stop_name = loc[0]
        long = loc[1]
        lat = loc[2]
        route = route_lookup_dict.get(stop_name)
        for r in route:
            r['stop_name'] = stop_name
            r['long'] = long
            r['lat'] = lat
        routes_available = [r.get('route') for r in route]
        all_routes_available.append([r for r in route])
        for r in routes_available:
            if r not in bus_priority.keys():
                bus_priority[r] = 1
            else:
                bus_priority[r] += 1
        bus_priority_list = sorted(bus_priority, key=bus_priority.get, reverse=True)

    for ra in all_routes_available:
        for r in ra:
            r['priority'] = bus_priority_list.index(r.get('route'))
        routing_queue.append(sorted(ra, key=lambda x: x['priority']))
        # print(ra)

    stop_num = 1
    for rq in routing_queue:
        r = rq[0]
        long = r.get('long')
        lat = r.get('lat')
        stop_name = r.get('stop_name')
        route = r.get('route')
        icon_color = route_colours.get(route)
        folium.Marker(
            location=[long, lat],
            popup= f"[{stop_num}]-{route}-{stop_name}",
            icon=folium.Icon(color=icon_color)
        ).add_to(m)
        stop_num += 1
        print(r)

    m.save(os.path.join(settings.BASE_DIR, 'scheduling', 'templates', 'maps.html'))
    return render(request, 'maps.html')


def search(request):
    start_position_query = request.GET.get('start_position')
    end_position_query = request.GET.get('end_position')
    print(start_position_query)
    print(end_position_query)

    stops_dict = {}
    for k, v in bus_stop_name_position_dict.items():
        stop_name = k
        long, lat = v[1], v[0]
        stops_dict[stop_name] = (long, lat)

    if request.method == 'GET':
        print("start position query is: ", start_position_query)
        print("end position query is: ", end_position_query)
        if start_position_query and end_position_query:
            start_query_url = f'https://nominatim.openstreetmap.org/search?q={start_position_query}&format=json&countrycodes=my'
            end_query_url = f'https://nominatim.openstreetmap.org/search?q={end_position_query}&format=json&countrycodes=my'
            start_longlat = requests.get(start_query_url).json()
            end_longlat = requests.get(end_query_url).json()

            for key in stops_dict.keys():
                if start_position_query in key:
                    start_longlat.append({'display_name': key, 'lat': stops_dict[key][0], 'lon': stops_dict[key][1], 'bus_stop': True})
                if end_position_query in key:
                    end_longlat.append({'display_name': key, 'lat': stops_dict[key][0], 'lon': stops_dict[key][1], 'bus_stop': True})

            return render(request, 'index.html', {
                'start_longlat': start_longlat,
                'end_longlat': end_longlat,
            })


def nearest_bus_stops(long, lat, n_stops):
    stops_distance = {}
    sorted_value_key_pairs = []
    for k, v in bus_stop_name_position_dict.items():
        stop_name = k
        stop_lon, stop_lat = v[1], v[0]
        distance_between = haversine(lat, long, float(stop_lat), float(stop_lon))
        stops_distance[stop_name] = distance_between
        value_key_pairs = ((value, key) for (key,value) in stops_distance.items())
        sorted_value_key_pairs = sorted(value_key_pairs)
    return sorted_value_key_pairs[:n_stops]


class Graph:
    def __init__(self):
        self.nodes = set()
        self.edges = {}
        self.distances = {}

    def add_node(self, value):
        self.nodes.add(value)
        self.edges[value] = []

    def add_edge(self, from_node, to_node, distance):
        self.edges[from_node].append(to_node)
        self.distances[(from_node, to_node)] = distance

    def dijkstra(self, initial_node):
        visited = {initial_node: 0}
        path = {}

        nodes = set(self.nodes)

        while nodes:
            min_node = None
            for node in nodes:
                if node in visited:
                    if min_node is None:
                        min_node = node
                    elif visited[node] < visited[min_node]:
                        min_node = node

            if min_node is None:
                break

            nodes.remove(min_node)
            current_weight = visited[min_node]

            for edge in self.edges[min_node]:
                weight = current_weight + self.distances[(min_node, edge)]
                if edge not in visited or weight < visited[edge]:
                    visited[edge] = weight
                    path[edge] = min_node

        return visited, path

    def shortest_path(self, start_node, end_node):
        distances, paths = self.dijkstra(start_node)
        path = [end_node]
        while path[-1] != start_node:
            path.append(paths[path[-1]])
        path.reverse()
        return path


def haversine(lat1, lon1, lat2, lon2):
    # convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # calculate haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371 # radius of Earth in kilometers
    distance = c * r

    return distance