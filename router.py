import pickle, re, sys, socket
from threading import Thread
from time import sleep
import datetime

IP = '127.0.0.1'
BASE_PORT = 0
INFINITY = 999
CONFIG_FILE = 'topology.config'
TIMEOUT = .05

NODES = 'ABCDEF'
table = {}
edges = {}

# Encode a message using pickle
def encode_message(msg_type, id, data):
    return pickle.dumps((msg_type, id, data))

# Decode a byte encoded message using pickle
def decode_message(raw_data):
    return pickle.loads(raw_data)

# Given an id, map it to the appropriate port
def get_port(id):
    return BASE_PORT + ord(id) - ord('A')

# Given an ID in the range A-F, map it to 0-5
def get_index(id):
    return ord(id) - ord('A')

# Given an index from 0-5, map it to IDs A-F
def get_id(index):
    return chr(index + ord('A'))

# Load the config file from disk, but only pick the line defining the node with id 'id'
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
                        edges[adj] = True
            else:
                print(f'Line {i+1} is incorrectly formatted')
        
        print('\nTable:')
        print_table(table)
        print()

# Print out a formatted table
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
            print('There is a negative cycle')
            return None
    
    return distance

# Given some data sent from an `sender`, update the table with new values present in `data`
def update_table(sender, data, addr):
    new_table = data
    
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
        print(f'\nRecieved table from IP:{addr} with ID:{sender}')
        print(f'Updated Table:')
        print_table(table)
    else:
        pass
    
    return updated

# Send an update each node that shares an edge with this node
def update_neighbors(sock):
    for neighbor, _cost in table[ID].items():
        # Skip if we do not share an edge with this node
        if not neighbor in edges:
            continue
        
        # Encode the id and table into byte format so it can be sent
        data = encode_message('update', ID, table)
        sock.sendto(data, (IP, get_port(neighbor)))

# Check for convergence, meaning that the adjacency matrix is symmetrical along the diagonal axis
def convergence(table):
    for a in NODES:
        for b in NODES:
            if table[a][b] != table[b][a] or table[a][b] == INFINITY or table[b][a] == INFINITY:
                return False
    return True

def router_simulation(sock):
    print('Press `Ctrl + C` to exit\nListening...')
    
    update_count = 0
    # Continue to run while we have not converged
    while not convergence(table):
        try:
            # Try to receive a message
            raw_data, addr = sock.recvfrom(1024)
            
            # Parse the table, which has been sent in an encoded byte format
            msg_type, id, data = decode_message(raw_data)
            
            # If we've recieved an update to the table, handle it
            if msg_type == 'update':
                # Try to update the table with new values
                updated = update_table(id, data, addr)
                
                # If the table was updated, send that updated table to our neighbors
                if updated:
                    update_count += 1
                    update_neighbors(sock)
            
            sleep(TIMEOUT)
        except TimeoutError:
            # Periodically update our neigbors
            update_neighbors(sock)
    return update_count

def test1(sock, update_count):
    # Broadcast only for router A for now...
    if ID == 'A':
        print('\n-------------------------\nTest 1:')
        msg = [ f'{ID}, {IP}, {PORT}', ('1001783662', 'Sameer ID'), datetime.datetime.now(), update_count, 1000 ]
        msg[4] = sys.getsizeof(msg)
        data = encode_message('broadcast', 'A', msg)
        
        sleep(1)
        
        for neighbor, _cost in table[ID].items():
            # Skip if we do not share an edge with this node
            if not neighbor in edges:
                continue
            
            sock.sendto(data, (IP, get_port(neighbor)))
    else:
        try:
            print('\n-------------------------\nTest 1:')
            while True:
                sock.settimeout(5)
                raw_data, _addr = sock.recvfrom(1024)
                msg_type, id, data = decode_message(raw_data)
                if msg_type != 'broadcast':
                    continue
                encoded_data = encode_message(msg_type, ID, data)
                print(f'Recieved broadcast from {id}')
                print(data[0], data[1], data[2], data[3], data[4], sep='\n')
                
                for neighbor, _cost in table[ID].items():
                    # Skip if we do not share an edge with this node
                    if not neighbor in edges:
                        continue
                    
                    sock.sendto(encoded_data, (IP, get_port(neighbor)))
                break
        except TimeoutError:
            print('No broadcast recieved')

# def broadcast_and_wait(sock, msg):
#     known_broadcasts = [msg]
#     sock.settimeout(1)
#     while True:
#         try:
#             for e in edges:
#                 encoded_data = encode_message('broadcast', ID, msg)
#                 sock.sendto(encoded_data, (IP, get_port(e)))
            
#             raw_data, _addr = sock.recvfrom(1024)
#             msg_type, _id, recv = decode_message(raw_data)
#             if msg_type == 'broadcast':
#                 if recv in known_broadcasts:
#                     break
            
#         except TimeoutError:
#             pass

# def test2(sock):
#     if ID == 'B':
#         del edges['D']
#         load_config(ID)
#         msg = ('link_broken', 'B', 'D')
#         broadcast_and_wait(sock, msg)
#     if ID == 'D':
#         del edges['B']
#         load_config(ID)
#         msg = ('link_broken', 'B', 'D')
#         broadcast_and_wait(sock, msg)
    
#     router_simulation(sock, True)

def test2(sock):
    print('\n-------------------------\nTest 2:')
    load_config(ID)
    if ID == 'A':
        del edges['B']
        table['A']['B'] = INFINITY
    elif ID == 'B':
        del edges['A']
        table['B']['A'] = INFINITY
    
    # Clear any messages from previous simulations
    sock.settimeout(.05)
    while True:
        try:
            sock.recvfrom(1024)
        except TimeoutError:
            break
    
    sleep(5)
    
    router_simulation(sock)

def main():
    if len(sys.argv) <= 2:
        print('Expected 2 arguments:\nrouter.py <PORT> <ID>')
        return
    
    # Read in command line arguments
    global BASE_PORT, PORT, ID
    try:
        PORT = int(sys.argv[1])
        ID = sys.argv[2]
        
        # Get base port (the port that the routers begin at, which is router 1)
        BASE_PORT = PORT - get_index(ID)
    except:
        print('Expected an integer')
        return
    
    # Load the config for this node
    load_config(ID)
    
    # Open a UDP socket on the given IP and port
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(TIMEOUT)
    sock.bind((IP, PORT))
    
    # Update neighbors after loading config
    update_neighbors(sock)
    
    update_count = 0
    try:
        # update_count = 0
        update_count = router_simulation(sock)
        
        test1(sock, update_count)

        test2(sock)
    except KeyboardInterrupt:
        pass
    
    print('\nUpdates:', update_count)
    sock.close()

if __name__ == "__main__":
    main()
