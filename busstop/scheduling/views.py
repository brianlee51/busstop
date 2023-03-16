from django.shortcuts import render, redirect
from django.conf import settings
import csv
import math
import folium
import os

# TODO: Make start position a red marker, and end position a green marker
# TODO: Use an API to show the curvature of the route between points
# TODO: Solve the "opposite" bus stop problem (nearest bus stops around you)
# TODO: Have a front end to allow user to set start point and end point?
# TODO: "straight line" distance calcuation is not the same as "road distance"
# TODO: If there's time make the front end better

# Create your views here.
def home(request):
    csv_path = os.path.join(settings.BASE_DIR, 'scheduling', 'bus_stop.csv')
    stops_csv = open(csv_path, 'r')
    reader = csv.DictReader(stops_csv)
    unique_stops = {}
    locations = []
    locations_longlat = []
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

    for row in reader:
        route = row['route']
        stop_id = row['stop_id']
        stop_name = row['name']
        long, lat = row['longlat'].split(',')
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

    start = request.GET.get('start')
    end = request.GET.get('end')
    if start and end:
        shortest_path = g.shortest_path(start, end)

        for p in shortest_path:
            locations.append((p, float(unique_stops.get(p)[0]), float(unique_stops.get(p)[1])))
            print(p, 'long:', unique_stops.get(p)[0], 'lat:', unique_stops.get(p)[1])
        
        m = folium.Map(location=(locations[0][1], locations[0][2]), zoom_start=13)

        stop = 1
        for loc in locations:
            if stop == 1:
                # set starting bus stop point to red marker
                folium.Marker(
                    location=[loc[1], loc[2]],
                    popup= "{0}-{1}".format(stop, loc[0]),
                    icon=folium.Icon(color='red')
                ).add_to(m)
            elif stop == len(locations):
                # set ending bus stop point to green marker
                folium.Marker(
                    location=[loc[1], loc[2]],
                    popup= "{0}-{1}".format(stop, loc[0]),
                    icon=folium.Icon(color='green')
                ).add_to(m)
            else:
                # set bus stop points to black marker
                folium.Marker(
                    location=[loc[1], loc[2]],
                    popup= "{0}-{1}".format(stop, loc[0]),
                    icon=folium.Icon(color=route_colours[route])
                ).add_to(m)
            stop += 1
            locations_longlat.append((loc[1], loc[2]))

        folium.PolyLine(locations_longlat, color='red').add_to(m)

        m.save(os.path.join(settings.BASE_DIR, 'scheduling', 'templates', 'maps.html'))
        if start and end:
            return render(request, 'maps.html')
    return render(request, 'index.html', {'unique_stops': unique_stops})


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