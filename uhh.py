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
                    # if ID != data[0] and ID != data[1]:
                    #     load_config(ID)
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

