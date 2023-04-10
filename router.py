# Steven Culwell
# 1001783662

import re
import sys

# Import socket module
import socket

graph = ()

# Import thread module
from threading import Thread

def multi_thread(connectionSocket):
    try:
        # Extract the path of the requested object from the message
        message = connectionSocket.recv(1024).decode('utf-8')
        print(message)
        
        connectionSocket.send('test'.encode('utf-8'))
    except Exception as e:
        print(f'{type(e).__name__}: {str(e)}')

    # Close the socket in case of some issues 
    connectionSocket.close()

def load_config():
    config = open('test.config')
    

def main():
    load_config()
    
    # Create a UDP server socket
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    # Assign a port number
    if len(sys.argv) <= 1:
        serverPort = 8080
    else:
        serverPort = int(sys.argv[1])

    # Bind the socket to server address and server port
    serverSocket.bind(('', serverPort)) # default to localhost

    # Listen to at most 5 connection at a time
    serverSocket.listen(5)

    # Server should be up and running and listening to the incoming connections
    print('Ready to serve')
    while True:
        '''This part is for multi threading'''
        conn, addr = serverSocket.accept()
        print(f'Connected to: {str(addr)}')
        print('Peer name:', conn.getpeername())
        print('Socket family:', conn.family)
        print('Socket protocol:', conn.proto)
        print('Timeout:', conn.gettimeout())
        thread = Thread(target=multi_thread, args=(conn,))
        '''Start the new thread'''
        thread.start()
    
    # Close server socket
    serverSocket.close()

if __name__ == '__main__':
    main()
