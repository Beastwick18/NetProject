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
                        # print(f'{curr} to {adj} costs {cost}')
                        # Update the value in the table
                        table[curr][adj] = cost
                        edges[adj] = True
            else:
                print(f'Line {i+1} is incorrectly formatted')
        
        # print('\nTable:')
        # print_table(table)
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
    
    # if updated:
    #     print(f'\nRecieved table from IP:{addr} with ID:{sender}')
    #     print(f'Updated Table:')
    #     print_table(table)
    # else:
    #     pass
    
    return updated

# Send an update each node that shares an edge with this node
def update_neighbors(sock):
    # Go through each of the nodes that share an edge with this node
    for neighbor in edges:
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

def router_simulation(sock, wait_for_broadcast = False, initial_broadcast = None):
    print('Press `Ctrl + C` to exit\nListening...')
    
    broadcast_index = 0
    if initial_broadcast is not None:
        print(f'Initially broadcast {initial_broadcast}')
        broadcast_msgs = {initial_broadcast: [edge for edge in edges]}
    else:
        broadcast_msgs = {}
    old_broadcasts = []
    update_count = 0
    # Continue to run while we have not converged
    while wait_for_broadcast or not convergence(table):
        try:
            # Try to receive a message
            raw_data, addr = sock.recvfrom(1024)
            
            # Parse the table, which has been sent in an encoded byte format
            msg_type, id, data = decode_message(raw_data)
            
            # First check if we are meant to wait for acknowledgement of previous broadcasts
            if msg_type == 'ack':
                if data in broadcast_msgs and id in broadcast_msgs[data]:
                    # Remove them from the pending acknowledgements
                    broadcast_msgs[data].remove(id)
                    # print(f'Ack from {id}')
                    
                    # If we require no more acknowledgements, remove this broadcast from the list
                    if not broadcast_msgs[data]:
                        print(f'{data} successfully fully broadcasted')
                        del broadcast_msgs[data]
                        old_broadcasts.append(data)
                        broadcast_index = 0
            elif msg_type == 'link_broken':
                if data in broadcast_msgs:
                    data = encode_message('ack', ID, data)
                    sock.sendto(data, (IP, get_port(id)))
                elif data not in old_broadcasts:
                    # Recieved new broadcast
                    wait_for_broadcast = False
                    print(f'New broadcast from {id}')
                    broadcast_msgs[data] = [edge for edge in edges]
                    broadcast_msgs[data].remove(id)
                    raw_data = encode_message('ack', ID, data)
                    sock.sendto(raw_data, (IP, get_port(id)))
                    
                    print(f'A link was broken from {data[0]} to {data[1]}, reset table')
                    
                    # Check if we aren't the node that has a broken link
                    if ID != data[0] and ID != data[1]:
                        load_config(ID)
                else:
                    # Already seen this broadcast, send acknowledgement
                    # print(f'Reack to {id}')
                    data = encode_message('ack', ID, data)
                    sock.sendto(data, (IP, get_port(id)))
                
            # If we've recieved an update to the table, handle it
            elif not broadcast_msgs and msg_type == 'update':
                # Try to update the table with new values
                updated = update_table(id, data, addr)
                
                # If the table was updated, send that updated table to our neighbors
                if updated:
                    update_count += 1
                    update_neighbors(sock)
            elif broadcast_msgs:
                # Rebroadcast
                for neighbor in edges:
                    msg = list(broadcast_msgs.items())[broadcast_index][0]
                    if neighbor in broadcast_msgs[msg]:
                        # print(f'Rebroadcast {broadcast_index} to {neighbor}: {("link_broken", ID, msg)}')
                        data = encode_message('link_broken', ID, list(broadcast_msgs.items())[broadcast_index][0])
                        sock.sendto(data, (IP, get_port(neighbor)))
            sleep(TIMEOUT)
        except TimeoutError:
            if broadcast_msgs:
                for neighbor in edges:
                    msg = list(broadcast_msgs.items())[broadcast_index][0]
                    if neighbor in broadcast_msgs[msg]:
                        # print(f'Rebroadcast {broadcast_index} to {neighbor}: {("link_broken", ID, msg)}')
                        data = encode_message('link_broken', ID, list(broadcast_msgs.items())[broadcast_index][0])
                        sock.sendto(data, (IP, get_port(neighbor)))
                    
                broadcast_index += 1
                if broadcast_index >= len(broadcast_msgs):
                    broadcast_index = 0
            else:
                # Periodically update our neigbors
                update_neighbors(sock)
    return update_count

def test1(sock, update_count):
    # Broadcast only for router A for now...
    if ID == 'A':
        sock.settimeout(1)
        print('\n-------------------------\nTest 1:')
        msg = [ f'{ID}, {IP}, {PORT}', ('1001783662', 'Sameer ID'), datetime.datetime.now(), update_count, 1000 ]
        msg[4] = sys.getsizeof(msg)
        data = encode_message('broadcast', 'A', msg)
        while True:
            for neighbor, _cost in table[ID].items():
                # Skip if we do not share an edge with this node
                if not neighbor in edges:
                    continue
                
                sock.sendto(data, (IP, get_port(neighbor)))
            
            raw_data, _addr = sock.recvfrom(1024)
            msg_type, id, msg2 = decode_message(raw_data)
            if msg_type == 'broadcast' and msg2 == msg:
                break
    else:
        print('\n-------------------------\nTest 1:')
        sock.settimeout(None)
        while True:
            raw_data, _addr = sock.recvfrom(1024)
            msg_type, id, data = decode_message(raw_data)
            if msg_type != 'broadcast':
                continue
            encoded_data = encode_message(msg_type, ID, data)
            print(f'Recieved broadcast from {id}')
            print(f'Broadcast info: {data[0]}')
            print(f'IDs: {data[1]}')
            print(f'UTC Time: {data[2]}')
            print(f'Updates: {data[3]}')
            print(f'Bytes: {data[4]}')
            
            for neighbor, _cost in table[ID].items():
                # Skip if we do not share an edge with this node
                if not neighbor in edges:
                    continue
                
                sock.sendto(encoded_data, (IP, get_port(neighbor)))
            break

def test2(sock):
    print('\n-------------------------\nTest 2:')
    
    
    # Clear any messages from previous simulations
    
    if ID == 'A':
        load_config(ID)
        del edges['B']
        table['A']['B'] = INFINITY
        router_simulation(sock, False, ('A', 'B'))
    elif ID == 'B':
        load_config(ID)
        del edges['A']
        table['B']['A'] = INFINITY
        router_simulation(sock, False, ('A', 'B'))
    else:
        router_simulation(sock, True)

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
