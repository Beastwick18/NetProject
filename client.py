# Steven Culwell
# 1001783662

import socket
import time
import sys

def main():
    # Parse command line arguments
    if len(sys.argv) == 3:
        HOST=sys.argv[1]
        PORT=8080
        fileName=sys.argv[2]
    elif len(sys.argv) == 4:
        HOST=sys.argv[1]
        PORT=int(sys.argv[2])
        fileName=sys.argv[3]
    else:
        print('Expected 2 or 3 arguments')
        return
    
    # Create client socket
    clientSocket = socket.socket()
    clientSocket.settimeout(1)

    print('Client has been established')
    print(f'Connecting to server, IP: {HOST}, PORT: {PORT}')
    server_add = (HOST, PORT)
    # connect the host and port to the socket
    clientSocket.connect(server_add)
    print('Peer name:', clientSocket.getpeername())
    print('Socket family:', clientSocket.family)
    print('Socket protocol:', clientSocket.proto)
    print('Timeout:', clientSocket.gettimeout())

    send_time = time.time()
    
    # Send GET request to server
    clientSocket.send(f'GET /{fileName} HTTP/1.1'.encode('utf-8'))

    # Recieve the header and data
    header = clientSocket.recv(1024).decode('utf-8')
    data = clientSocket.recv(1024).decode('utf-8')
    recv_time = time.time()
    # Calculate the round trip time
    RTT = recv_time - send_time
    
    # Parse the header
    headerLines = header.splitlines()
    if headerLines[0] == 'HTTP/1.0 404 Not Found':
        print('Response: 404 Not found')
    elif headerLines[0] == 'HTTP/1.0 400 Bad Request':
        print('Response: 400 Bad Request')
    elif headerLines[0] == 'HTTP/1.0 200 OK':
        print('Response: 200 OK')
    
    # Sometimes, the header and content messages will be combined,
    # depending on how quickly they were sent. If they were both
    # combined into one message (the header), set the data to be
    # the content after the header.
    if len(headerLines) > 2: # There is data past the header (first two lines)
        data = ''
        for line in headerLines[2:]:
            data += line + '\n'
    
    print(f'Data received by the client is:\n{data}')
    print(f'RTT {RTT} seconds')

    ''' close socket '''
    clientSocket.close()

if __name__ == "__main__":
    main()
