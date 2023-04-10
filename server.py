# Steven Culwell
# 1001783662

import re
import sys

# Import socket module
import socket

# Import thread module
from threading import Thread

def bad_request_response(connectionSocket, error):
    print('400 Bad Request')
    connectionSocket.send('HTTP/1.1 400 Bad Request\r\n\r\n'.encode('utf-8'))
    connectionSocket.send(f'<html><body><h1>Error 400: Bad Request</h1><p>{error}</p></body></html>\r\n'.encode("utf-8"))

def not_found_response(connectionSocket, error):
    print('404 Not Found')
    connectionSocket.send('HTTP/1.1 404 Not Found\r\n\r\n'.encode('utf-8'))
    connectionSocket.send(f'<html><body><h1>Error 404: Not Found</h1><p>{error}</p></body></html>\r\n'.encode("utf-8"))

def ok_response(connectionSocket, filename):
    connectionSocket.send(f'HTTP/1.1 200 OK\r\n\r\n'.encode('utf-8'))

def parse_request(message):
    lines = message.splitlines()
    for line in lines:
        # Check if the line matches GET /(filename) ...
        if match := re.match(r'GET /([\w\.\-/]*) .*', line):
            filename = match.group(1)
            if not filename:
                return (404, 'No file name given')
            
            return (200, filename)
    return (400, 'Invalid GET request')

def multi_thread(connectionSocket):
    try:
        # Extract the path of the requested object from the message
        message = connectionSocket.recv(1024).decode('utf-8')
        print(message)
        response_code, response = parse_request(message)
        
        # If there was an error parsing the message, return the appropriate header
        if response_code == 404:
            not_found_response(connectionSocket, response)
            connectionSocket.close()
            return
        if response_code == 400:
            bad_request_response(connectionSocket, response)
            connectionSocket.close()
            return

        # Store the entire content of the requested file in a temporary buffer
        filename = response
        f = open(f'./{filename}', 'rb')
        outputdata = f.read()

        # Send the HTTP response header line to the connection socket
        print('Sending header...')
        ok_response(connectionSocket, f.name)
        
        # Send the content of the requested file to the connection socket
        print('Sending file...')
        connectionSocket.send(outputdata)
    except Exception as e:
        error = f'{type(e).__name__}: {str(e)}'
        not_found_response(connectionSocket, error)

    # Close the socket in case of some issues 
    connectionSocket.close()

def main():
    # Create a TCP server socket
    serverSocket = socket.socket()

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
