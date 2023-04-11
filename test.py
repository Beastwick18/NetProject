import pickle
import re
import sys
import socket
from threading import Thread
from time import sleep

IP = '127.0.0.1'
BASE_PORT = 0
INFINITY = 999
CONFIG_FILE = 'test.config'
TIMEOUT = 1

NODES = 'ABCDEF'
table = {}

def get_port(id):
    if id < 'A' or id > 'F':
        print('The given ID is not within the range of valid IDs')
        return
    
    return BASE_PORT + ord(id) - ord('A')

def get_index(id):
    if id < 'A' or id > 'F':
        print('The given ID is not within the range of valid IDs')
        return
    
    return ord(id) - ord('A')

def get_id(index):
    return chr(index + ord('A'))

def load_config(id):
    # Initialize the table
    for node in NODES:
        table[node] = {}
    
    # Set all nodes to have an infinite cost to each neighbor node
    for node in NODES:
        for node2 in NODES:
            table[node][node2] = INFINITY
    
    # Change the cost to 0 when going from one node to itself
    for node in NODES:
        table[node][node] = 0
    
    # Open the config file
    with open(CONFIG_FILE) as config:
        # Split the file into individual lines to be parsed
        lines = config.read().splitlines()
        
        for i, line in enumerate(lines):
            # Check if line is correctly formatted, while also getting the node this line is defining,
            # as well as the data within the `{}` after it. Will fail if the line is improperly formatted.
            if match := re.match(r'([A-F])={([A-F]:[0-9]+(,[A-F]:[0-9]+)*)}', line):
                # Get the node that this line is defining
                curr = match.group(1)
                
                # Only consider the line defining this routers node
                if curr != ID:
                    continue
                
                # Get all the neighbors of this node, which are comma delimeted
                neighbors = match.group(2).split(',')
                for n in neighbors:
                    # Check if the neighbors data is properly formatted, i.e. NEIGHBOR:COST
                    if match := re.match(r'([A-F]):([0-9]+)', n):
                        # Get the neighbor in question
                        adj = match.group(1)
                        # Get that neighbors cost
                        cost = int(match.group(2))
                        print(f'{curr} to {adj} costs {cost}')
                        # Update the value in the table
                        table[curr][adj] = cost
            else:
                print(f'Line {i+1} is incorrectly formatted')
        
        print('\nTable:')
        print_table(table)
        print()

def print_table(table):
    for key, value in table.items():
        print(str(key) + ' ' + str(value))

# Source: https://en.wikipedia.org/wiki/Bellman%E2%80%93Ford_algorithm
def bellman_ford(table, source):
    vertices = NODES
    distance = [INFINITY] * len(vertices)
    predecessor = [None] * len(vertices)
    
    distance[source] = 0
    
    for _ in range(len(vertices)-1):
        for node, edges in table.items():
            u = get_index(node)
            for edge, w in edges.items():
                v = get_index(edge)
                if distance[u] + w < distance[v]:
                    distance[v] = distance[u] + w
                    predecessor[v] = u
    
    for node in vertices:
        v = get_index(node)
        u = predecessor[v]
        if u != None and distance[u] + table[get_id(u)][node] < distance[v]:
            print('ruh roh, negative cycle')
            return None
    
    return distance

def update_table(data, addr):
    sender = data[0]
    new_table = data[1]
    
    updated = False
    for node, edges in new_table.items():
        for edge, cost in edges.items():
            if cost < table[node][edge]:
                updated = True
                table[node][edge] = cost
    
    distance = bellman_ford(table, get_index(ID))
    for i, cost in enumerate(distance):
        v = NODES[i]
        if cost < table[ID][v]:
            table[ID][v] = cost
            updated = True
    
    if updated:
        print(f'Recieved table from IP:{addr} with ID:{sender}')
        print(f'\nUpdated Table:')
        print_table(table)
    else:
        pass
        # print('No updates')
    return updated

def update_neighbors(sock):
    for neighbor, cost in table[ID].items():
        # Don't send to itself, and don't send to node that cannot be reached
        if neighbor == ID or cost == INFINITY:
            continue
        
        # Encode the id and table into byte format so it can be sent
        data = pickle.dumps((ID, table))
        sock.sendto(data, (IP, get_port(neighbor)))

def main():
    if len(sys.argv) <= 2:
        print('Expected 2 arguments:\nrouter.py <PORT> <ID>')
        return
    
    global BASE_PORT, PORT, ID
    try:
        PORT = int(sys.argv[1])
        ID = sys.argv[2]
        
        # Get base port (the port that the routers begin at, which is router 1)
        BASE_PORT = PORT - get_index(ID)
    except:
        print('Expected an integer')
        return
    
    load_config(ID)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(TIMEOUT)
    sock.bind((IP, PORT))
    
    try:
        print('Press `Ctrl + C` to exit\nListening...')
        
        while True:
            try:
                raw_data, addr = sock.recvfrom(1024)
                
                # Parse the table, which has been sent in an encoded byte format
                data = pickle.loads(raw_data)
                
                # Try to update the table with new values
                updated = update_table(data, addr)
                
                sleep(TIMEOUT)
                
                if updated:
                    update_neighbors(sock)
            except TimeoutError:
                # On timeout, update neighbors with our routing table
                update_neighbors(sock)
    except KeyboardInterrupt:
        pass
    
    sock.close()

if __name__ == "__main__":
    main()
