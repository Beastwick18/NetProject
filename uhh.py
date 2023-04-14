
def router_simulation(sock):
    print('Press `Ctrl + C` to exit\nListening...')
    
    no_update = False
    sock.settimeout(TIMEOUT)
    update_count = 0
    # Continue to run while we have not converged
    while update_count == 0 or not convergence(table):
        try:
            # Try to receive a message
            raw_data, addr = sock.recvfrom(1024)
            
            # Parse the table, which has been sent in an encoded byte format
            msg_type, id, data = decode_message(raw_data)
            
            # If we've recieved an update to the table, handle it
            if not no_update and msg_type == 'update':
                # Try to update the table with new values
                updated = update_table(id, data, addr)
                
                # If the table was updated, send that updated table to our neighbors
                if updated:
                    update_count += 1
                    update_neighbors(sock)
            elif msg_type == 'link_cut':
                no_update = True
                u, v = data
                print(f'Recieved cut link notice from {id}: Link {u}->{v} was cut')
                
                encoded_data = encode_message(msg_type, ID, data)
                encoded_ack = encode_message('ack', ID, (u, ID))
                
                load_config(ID)
                
                for neighbor, _cost in table[ID].items():
                    # Skip if we do not share an edge with this node
                    if not neighbor in edges:
                        continue
                    
                    sock.sendto(encoded_ack, (IP, get_port(neighbor)))
                    sleep(1)
                    sock.sendto(encoded_data, (IP, get_port(neighbor)))
            elif msg_type == 'ack':
                if data[0] == ID:
                    no_update = False
                else:
                    encoded_ack = encode_message('ack', ID, data)
                    
                    for neighbor, _cost in table[ID].items():
                        # Skip if we do not share an edge with this node
                        if not neighbor in edges:
                            continue
                        
                        sock.sendto(encoded_ack, (IP, get_port(neighbor)))
                
            sleep(TIMEOUT)
        except TimeoutError:
            # Periodically update our neigbors
            if not no_update:
                update_neighbors(sock)
    return update_count

def cut_link(sock, id):
    # reset the config
    load_config(ID)
    
    # delete the cut edge
    del edges[id]
    table[ID][id] = INFINITY
    
    sock.settimeout(10)
    # Try to broadcast that this link was cut to all routers 3 times, give up after that
    attempts = 0
    while attempts < 3:
        try:
            acks = {}
            
            msg = (ID, id)
            data = encode_message('link_cut', ID, msg)
            
            for neighbor, _cost in table[ID].items():
                # Skip if we do not share an edge with this node
                if not neighbor in edges:
                    continue
                
                sock.sendto(data, (IP, get_port(neighbor)))
            
            while True:
                for n in NODES:
                    if n != ID and n != id and n not in acks:
                        return
                raw_data, _addr = sock.recvfrom(1024)
                msg_type, id, data = decode_message(raw_data)
                if msg_type == 'ack':
                    if data[0] == ID and not acks[data[1]]:
                        acks[data[1]] = True
                        print(acks)
                    else:
                        encoded_ack = encode_message('ack', ID, data)
                        
                        for neighbor, _cost in table[ID].items():
                            # Skip if we do not share an edge with this node
                            if not neighbor in edges:
                                continue
                            
                            sock.sendto(encoded_ack, (IP, get_port(neighbor)))
                        
        except TimeoutError:
            attempts += 1
            print(f'Attempt {attempts+1} failed, did not get acknowledgement from all routers')
    else:
        print("Gave up, did not get acknowledgement from all routers")

def test2(sock):
    print('\n-------------------------\nTest 2:')
    if ID == 'B':
        cut_link(sock, 'D')
    elif ID == 'D':
        cut_link(sock, 'B')
    else:
        router_simulation(sock, True)
    
    router_simulation(sock)
    print_table(table)

