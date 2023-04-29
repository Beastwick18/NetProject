import pickle, re, sys, socket
from threading import Thread
from time import sleep
import datetime

# The IP address that all routers will be using (localhost)
IP = '127.0.0.1'

# The port from which we start counting. This should be the port of the first
# router, which is usually 'A'
BASE_PORT = 0

# A value to represent an infinite cost to get from one node to another
INFINITY = 999

# The name of our config file
CONFIG_FILE = 'topology.config'

# The default timeout before we give up on recieving a message, and also
# how long we wait until listening for another message. Measured in seconds
TIMEOUT = .5

# All valid nodes
NODES = 'ABCDEF'

# The table containing the cost from each node to each other node
table = {}

# The list of nodes which share an edge with this node
edges = {}

# Encode a message using pickle
def encode_message(msg_type, id, data):
    return pickle.dumps((msg_type, id, data))

# Decode a byte encoded message using pickle
def decode_message(raw_data):
    return pickle.loads(raw_data)

# Encode and send a message on socket `sock`, to `destination`, with messsage
# type `msg_type`, containing `data`
def send_message(sock, destination, msg_type, data):
    encoded_data = encode_message(msg_type, ID, data)
    sock.sendto(encoded_data, (IP, get_port(destination)))

# Recieve some message on socket `sock` and decode it
def recieve_message(sock):
    raw_data, _addr = sock.recvfrom(1024)
    
    # Parse the message, which has been sent in an encoded byte format
    return decode_message(raw_data)

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
        print('Loading config file topology.config:')
        file = config.read()
        print(file)
        # Split the file into individual lines to be parsed
        lines = file.splitlines()
        
        for i, line in enumerate(lines):
            # Check if line is correctly formatted, while also getting the node this line is defining,
            # as well as the data within the `{}` after it. Will fail if the line is improperly formatted.
            if match := re.match(r'([A-Z])={([A-Z]:[0-9]+(,[A-Z]:[0-9]+)*)}', line):
                # Get the node that this line is defining
                curr = match.group(1)
                
                # Only consider the line defining this routers node
                if curr != ID:
                    continue
                
                # Get all the neighbors of this node, which are comma delimeted
                neighbors = match.group(2).split(',')
                for n in neighbors:
                    # Check if the neighbors data is properly formatted, i.e. NEIGHBOR:COST
                    if match := re.match(r'([A-Z]):([0-9]+)', n):
                        # Get the neighbor in question
                        adj = match.group(1)
                        # Get that neighbors cost
                        cost = int(match.group(2))
                        # Update the value in the table
                        table[curr][adj] = cost
                        edges[adj] = True
            else:
                print(f'Line {i+1} is incorrectly formatted')

# Print out a formatted table
def print_table(table):
    for key, value in table.items():
        print(f'{key} {value}')

# Bellman ford algorithm for minimizing cost
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

# Given some data sent from an `sender`, update the table with new values present in `new_table`
def update_table(sender, new_table):
    updated = False

    # Go through each cost and replace it with the updated table's cost if it is lower
    for node, edges in new_table.items():
        for edge, cost in edges.items():
            if cost < table[node][edge]:
                print(f'Updated: Source={sender}, Current={edge}:{cost}, Previous={edge}:{table[node][edge]}')
                updated = True
                table[node][edge] = cost

    # Perform the bellman ford algorithm to replace costs with the cost to reach by traversing one node ahead,
    # but only if it is a lower cost
    distance = bellman_ford(table, get_index(ID))
    for i, cost in enumerate(distance):
        v = NODES[i]
        if cost < table[ID][v]:
            print(f'Updated: Source={sender}, Current={v}:{cost}, Previous={v}:{table[ID][v]}')
            table[ID][v] = cost
            updated = True
    
    # Return whether or not any changes were made, so that we can decide whether or not to update our neighbors
    return updated

# Send an update each node that shares an edge with this node
def update_neighbors(sock):
    # Go through each of the nodes that share an edge with this node
    for neighbor in edges:
        # Send an updated table to this neighbor
        send_message(sock, neighbor, 'update', table)

# Check for convergence, meaning that the adjacency matrix is symmetrical along the diagonal axis
# and there are no nodes marked as infinity
def convergence(table):
    for a in NODES:
        for b in NODES:
            if table[a][b] != table[b][a] or table[a][b] == INFINITY:
                return False
    return True

# Perform a router simulation.
def router_simulation(sock):
    print('Press `Ctrl + C` to exit\nListening...')
    
    # Keep track of the total number of updates to the table
    update_count = 0
    
    # Continue to run while we have not converged, or while we are waiting for a broadcast
    while not convergence(table):
        try:
            # Try to receive a message
            msg_type, id, data = recieve_message(sock)
            
            # If we've recieved an update to the table, handle it
            if msg_type == 'update':
                # Try to update the table with new values
                updated = update_table(id, data)
                
                # If the table was updated, send that updated table to our neighbors
                if updated:
                    update_count += 1
                    update_neighbors(sock)
            # If we still have broadcasts waiting on acknowledgements, timeout and resend them
            sleep(TIMEOUT)
        except TimeoutError:
            # Periodically update our neigbors
            update_neighbors(sock)
    return update_count

# Recieve a broadcast that matches broadcast_type
def recv_broadcast(sock, broadcast_type):
    while True:
        try:
            msg_type, id, data = recieve_message(sock)
            # Keep waiting until we find a broadcast message that is the correct type
            # of broadcast
            if msg_type != 'broadcast' or data[0] != broadcast_type:
                continue
            
            # Return it and its sender
            return data, id
        except TimeoutError:
            pass
    pass

# Send a broadcast to broadcast_msg. `sender` is the node we have recieved the broadcast
# from. It can be None, which means we are the original source of the broadcast.
def broadcast(sock, sender, broadcast_msg):
    # Keep track of which neighbors we are waiting for acknowledgement from
    pending_acks = [edge for edge in edges]
    
    # Send the broadcast to each neighbor
    for neighbor in pending_acks:
        send_message(sock, neighbor, 'broadcast', broadcast_msg)
    
    # Check if we originally recieved the broadcast from another node. In this case,
    # we would not need acknowledgement from them, because we know they have seen
    # the broadcast.
    if sender != None:
        pending_acks.remove(sender)
    
    # Keep going as long as we still need acknowledgement from neighbors
    while pending_acks:
        try:
            print(f'Waiting on {pending_acks}')
            msg_type, id, msg = recieve_message(sock)
            
            # Check that we have recieved a broadcast and it is the same as ours
            if msg_type == 'broadcast' and msg == broadcast_msg:
                # If we were waiting for acknowledgement from this neighbor, mark them as acknowledged
                if id in pending_acks:
                    pending_acks.remove(id)
                # Otherwise, send them back the broadcast as acknowledgement
                else:
                    send_message(sock, id, 'broadcast', broadcast_msg)
        except TimeoutError:
            # Periodically send out the broadcast, as long as we are still waiting for
            # acknowledgement
            for neighbor in pending_acks:
                send_message(sock, neighbor, 'broadcast', broadcast_msg)

def test1(sock, update_count):
    print('\n-------------------------\nTest 1:')
    sock.settimeout(TIMEOUT)
    
    # Broadcast from router A
    if ID == 'A':
        # Create the broadcast message
        msg = [ 'message', f'{ID}, {IP}, {PORT}', ('1001783662', '1002015854'), datetime.datetime.now(), update_count, 1000 ]
        msg[5] = sys.getsizeof(msg)
        print(f'Sending broadcast:')
        print(f'Broadcast info: {msg[1]}')
        print(f'IDs: {msg[2]}')
        print(f'UTC Time: {msg[3]}')
        print(f'Updates: {msg[4]}')
        print(f'Bytes: {msg[5]}\n')
        
        # Broadcast the message to our neighbors
        broadcast(sock, None, msg)
    else:
        # Recieve a broadcast
        msg, recv_from = recv_broadcast(sock, 'message')
        _, info, ids, utc, updates, num_bytes = msg
        
        print(f'Recieved broadcast from {recv_from}')
        print(f'Broadcast info: {info}')
        print(f'IDs: {ids}')
        print(f'UTC Time: {utc}')
        print(f'Updates: {updates}')
        print(f'Bytes: {num_bytes}\n')
        
        # Send that broadcast to our neighbors, except the sender
        broadcast(sock, recv_from, msg)
    print('\nSuccessfully broadcast message\n')
    sleep(4)

# Simulate a link being broken between nodes u and v
def break_link(u, v):
    # Reload the config
    load_config(ID)
    # Remove the edge they share
    del edges[v]
    # Set the cost from one to the other as INFINITY
    table[u][v] = INFINITY
    # Put in ascending order so that break_link(u, v) == break_link(v, u)
    if u > v:
        u, v = v, u
    return ('link_broken', u, v)

def test2(sock):
    print('\n-------------------------\nTest 2:')
    
    sock.settimeout(TIMEOUT)
    
    # For nodes A and B, broadcast that a link has been broken between the two
    if ID == 'A':
        broadcast(sock, None, break_link('A', 'B'))
    elif ID == 'B':
        broadcast(sock, None, break_link('B', 'A'))
    else:
        # For all other nodes, recieve the broadcast that a link was broken, and
        # clear the table. Rebroadcast to our neighbors.
        broken_link_msg, recv_from = recv_broadcast(sock, 'link_broken')
        
        print(f'Recieved notice of broken link: {broken_link_msg}')
        load_config(ID)
        
        broadcast(sock, recv_from, broken_link_msg)
    
    sleep(4)
    print()
    
    # Afterwards, work back towards convergence now that the table has changed
    router_simulation(sock)
    
    print('\nReached convergence:')
    print_table(table)

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
    
    # Open a UDP socket on the given IP and port
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(TIMEOUT)
    sock.bind((IP, PORT))
    
    # Load the config for this node
    load_config(ID)
    
    # Update neighbors after loading config
    update_neighbors(sock)
    
    update_count = 0
    try:
        print_table(table)
        update_count = router_simulation(sock)
        print('\nReached convergence:')
        print_table(table)
        
        test1(sock, update_count)

        test2(sock)
    except KeyboardInterrupt:
        pass
    
    sock.close()

if __name__ == "__main__":
    main()
