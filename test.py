import sys
from threading import Thread
from time import sleep
import socket
import re
import pickle

BASE_PORT = 0
INFINITY = 999

nodes = 'ABCDEF'
table = {}

def get_port(id):
    if id < 'A' or id > 'F':
        print('The given ID is not within the range of valid IDs')
        return
    
    return BASE_PORT + ord(id) - ord('A')

def load_config(id):
    # Initialize the table
    for node in nodes:
        table[node] = {}
    
    # Set all nodes to have an infinite cost to each neighbor node
    for node in nodes:
        for node2 in nodes:
            table[node][node2] = INFINITY
    
    # Change the cost to 0 when going from one node to itself
    for node in nodes:
        table[node][node] = 0
    
    # Open the config file
    with open('test.config') as config:
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
                        cost = match.group(2)
                        print(f'{curr} to {adj} costs {cost}')
                        # Update the value in the table
                        table[curr][adj] = cost
            else:
                print(f'Line {i+1} is incorrectly formatted')
        
        print(table)

def main():
    if len(sys.argv) <= 2:
        print('Expected 2 arguments:\nrouter.py <PORT> <ID>')
        return
    
    global BASE_PORT, PORT, ID
    try:
        PORT = int(sys.argv[1])
        ID = sys.argv[2]
        
        # Get base port (the port that the routers begin at, which is router 1)
        BASE_PORT = PORT - ord(ID) + ord('A')
    except:
        print('Expected an integer')
        return
    
    load_config(ID)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1)
    sock.bind(('127.0.0.1', PORT))
    
    try:
        print('Press `Ctrl + C` to exit\nListening...')
        
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                print(f'wow: {pickle.loads(data)}, {addr}')
            except TimeoutError:
                # On timeout, update neighbors with our routing table
                for x, v in table[ID].items():
                    if x != ID and v != INFINITY:
                        data = pickle.dumps(table)
                        sock.sendto(data, ('127.0.0.1', get_port(x)))
    except KeyboardInterrupt:
        pass
    
    sock.close()

if __name__ == "__main__":
    main()
