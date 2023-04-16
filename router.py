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

def send_message(sock, destination, msg_type, data):
    encoded_data = encode_message(msg_type, ID, data)
    sock.sendto(encoded_data, (IP, get_port(destination)))

def recieve_message(sock):
    raw_data, _addr = sock.recvfrom(1024)
    
    # Parse the table, which has been sent in an encoded byte format
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

# Given some data sent from an `sender`, update the table with new values present in `new_table`
def update_table(sender, new_table):
    # Go through each cost and replace it with the updated table's cost if it is lower
    updated = False
    for node, edges in new_table.items():
        for edge, cost in edges.items():
            if cost < table[node][edge]:
                print(f'Updated: Source={sender}, Current={cost}, Previous={table[node][edge]}')
                updated = True
                table[node][edge] = cost

    # Perform the bellman ford algorithm to replace costs with the cost to reach by traversing one node ahead, but only if it is a lower cost
    distance = bellman_ford(table, get_index(ID))
    for i, cost in enumerate(distance):
        v = NODES[i]
        if cost < table[ID][v]:
            print(f'Updated: Source={sender}, Current={cost}, Previous={table[ID][v]}')
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
def convergence(table):
    for a in NODES:
        for b in NODES:
            if table[a][b] != table[b][a] or table[a][b] == INFINITY or table[b][a] == INFINITY:
                return False
    return True

# Perform a router simulation.
# wait_for_broadcast indicates if we should wait for at least one broadcast to be recieved before
# considering whether or not convergence has been achieved. This is used for when we are expecting
# a link break to occur while the router may have aleardy reached convergence.
# initial_broadcast contains a broadcast that we are meant to send out on the first update. This is
# used for when we are meant to initially broadcast a link break.
def router_simulation(sock, wait_for_broadcast = False, initial_broadcast = None):
    print('Press `Ctrl + C` to exit\nListening...')
    
    # Initialize broadcast_msgs to contain the initial_broadcast, only if it is present
    if initial_broadcast is not None:
        print(f'Initially broadcast {initial_broadcast}')
        # The broadcast must be populated with all the edges that this node contains, so that we
        # can check them off for acknowledgement
        broadcast_msgs = {initial_broadcast: [edge for edge in edges]}
    else:
        broadcast_msgs = {}
    
    # Keep track of broadcasts we have already sent and recieved acknowledgement for so that we do
    # not send them out again
    old_broadcasts = []
    
    # Keep track of the total number of updates to the table
    update_count = 0
    
    # Continue to run while we have not converged, or while we are waiting for a broadcast
    while wait_for_broadcast or not convergence(table):
        try:
            # Try to receive a message
            msg_type, id, data = recieve_message(sock)
            
            # First check if we have recieved an acknowledgement from one of our peers
            if msg_type == 'ack':
                # Check that we are still waiting for an acknowledgement from this peer for
                # this specific broadcast
                if data in broadcast_msgs and id in broadcast_msgs[data]:
                    # Remove them from the pending acknowledgements
                    broadcast_msgs[data].remove(id)
                    print(f'Ack from {id}')
                    
                    # If we require no more acknowledgements, move this broadcast to old_broadcasts
                    if not broadcast_msgs[data]:
                        print(f'{data} successfully fully broadcasted')
                        del broadcast_msgs[data]
                        old_broadcasts.append(data)
            # Otherwise, check if we have recieved a notice that a link was broken.
            elif msg_type == 'link_broken':
                # First check if we are aware of this and still waiting for acknowledgement
                if data in broadcast_msgs:
                    # We are aware already, so acknowledge
                    send_message(sock, id, 'ack', data)
                # Otherwise, check that we haven't already seed this at all
                elif data not in old_broadcasts:
                    # Recieved new broadcast
                    wait_for_broadcast = False
                    print(f'New broadcast from {id}')
                    
                    # Add this broadcast to the list of broadcasts
                    broadcast_msgs[data] = [edge for edge in edges]
                    broadcast_msgs[data].remove(id)
                    send_message(sock, id, 'ack', data)
                    if not broadcast_msgs[data]:
                        print(f'{data} successfully fully broadcasted')
                        del broadcast_msgs[data]
                        old_broadcasts.append(data)
                        
                    
                    print(f'A link was broken from {data[0]} to {data[1]}, reset table')
                    
                    # Check if we aren't the node that has a broken link
                    if ID != data[0] and ID != data[1]:
                        load_config(ID)
                else:
                    # Already seen this broadcast, send acknowledgement
                    print(f'Reack to {id}')
                    send_message(sock, id, 'ack', data)
                
            # If we've recieved an update to the table, handle it
            elif not broadcast_msgs and msg_type == 'update':
                # Try to update the table with new values
                updated = update_table(id, data)
                
                # If the table was updated, send that updated table to our neighbors
                if updated:
                    update_count += 1
                    update_neighbors(sock)
            # If we still have broadcasts waiting on acknowledgements, timeout and resend them
            elif broadcast_msgs:
                # Rebroadcast
                raise TimeoutError
            sleep(TIMEOUT)
        except TimeoutError:
            # If we still have messages to broadcast, broadcast one at the head of the list
            # to each neighbor that we are missing an acknowledgement from
            if broadcast_msgs:
                msg = list(broadcast_msgs.items())[0][0]
                for neighbor in broadcast_msgs[msg]:
                    print(f'Rebroadcast {msg} to {neighbor}: {("link_broken", ID, msg)}')
                    send_message(sock, neighbor, 'link_broken', msg)
            else:
                # Periodically update our neigbors
                update_neighbors(sock)
    return update_count

def test1(sock, update_count):
    # Broadcast from router A
    if ID == 'A':
        sock.settimeout(TIMEOUT)
        print('\n-------------------------\nTest 1:')
        msg = [ f'{ID}, {IP}, {PORT}', ('1001783662', 'Sameer ID'), datetime.datetime.now(), update_count, 1000 ]
        msg[4] = sys.getsizeof(msg)
        pending_acks = [edge for edge in edges]
        for neighbor in pending_acks:
            send_message(sock, neighbor, 'broadcast', msg)
        while pending_acks:
            try:
                msg_type, id, msg2 = recieve_message(sock)
                if msg_type == 'broadcast' and msg2 == msg:
                    if id in pending_acks:
                        pending_acks.remove(id)
                    else:
                        send_message(sock, id, 'broadcast', msg)
            except TimeoutError:
                for neighbor in pending_acks:
                    send_message(sock, neighbor, 'broadcast', msg)
    else:
        print('\n-------------------------\nTest 1:')
        sock.settimeout(TIMEOUT)
        pending_acks = [edge for edge in edges]
        recv_from = ''
        
        msg = None
        while True:
            try:
                msg_type, id, data = recieve_message(sock)
                recv_from = id
                if msg_type != 'broadcast':
                    continue
                print(f'Recieved broadcast from {id}')
                print(f'Broadcast info: {data[0]}')
                print(f'IDs: {data[1]}')
                print(f'UTC Time: {data[2]}')
                print(f'Updates: {data[3]}')
                print(f'Bytes: {data[4]}')
                msg = data
                
                break
            except TimeoutError:
                pass
        
        for neighbor in pending_acks:
            send_message(sock, neighbor, 'broadcast', msg)
        pending_acks.remove(recv_from)
        while pending_acks:
            try:
                print(f'Waiting on {pending_acks}')
                msg_type, id, msg2 = recieve_message(sock)
                if msg_type == 'broadcast' and msg2 == msg:
                    if id in pending_acks:
                        pending_acks.remove(id)
                    else:
                        send_message(sock, id, 'broadcast', msg)
            except TimeoutError:
                for neighbor in pending_acks:
                    send_message(sock, neighbor, 'broadcast', msg)
    print('\ndone\n')
    sleep(4)

def test2(sock):
    print('\n-------------------------\nTest 2:')
    
    print_table(table)
    
    sock.settimeout(TIMEOUT)
    if ID == 'A':
        load_config(ID)
        del edges['B']
        table['A']['B'] = INFINITY
        router_simulation(sock, False, ('A', 'B'))
    elif ID == 'B':
        load_config(ID)
        del edges['A']
        table['B']['A'] = INFINITY
        router_simulation(sock, False, ('B', 'A'))
    else:
        router_simulation(sock, True)
    
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
        # update_count = 0
        print_table(table)
        update_count = router_simulation(sock)
        print_table(table)
        
        test1(sock, update_count)

        test2(sock)
    except KeyboardInterrupt:
        pass
    
    # print('\nUpdates:', update_count)
    sock.close()

if __name__ == "__main__":
    main()
