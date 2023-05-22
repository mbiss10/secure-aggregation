#######################################################################################################################
# Author: Maurice Snoeren                                                                                             #
# Version: 0.2 beta (use at your own risk)                                                                            #
#                                                                                                                     #
# MyOwnPeer2PeerNode is an example how to use the p2pnet.Node to implement your own peer-to-peer network node.        #
# 28/06/2021: Added the new developments on id and max_connections
#######################################################################################################################
import time
from p2pnetwork.node import Node
import json 
import threading
import random

from pprint import pprint

CRYPTOGRAPHIC_BASE = 2**10 - 1 

class SecAggPeer(Node):

    # Python class constructor
    def __init__(self, host, port, id=None, value=100, callback=None, max_connections=0, connect_to_addr=None, connect_to_port=None):
        super(SecAggPeer, self).__init__(host, port, id, callback, max_connections)

        self.lock = threading.Lock()

        self.connected = set()

        if connect_to_addr != None and connect_to_port != None:
            self.connected.add((connect_to_addr, connect_to_port))
            self.connect_with_node(connect_to_addr, connect_to_port)

        self.sent_sub_masks = {}
        self.received_sub_masks = {}

        self.received_aggragated_values = {}

        self.value = value

        self._set_of_connections = set()

        print("SecAggPeer: Started")

    # When a new node connects to us, we want to send the new a list of all inbound or outbound connections. The
    # new node thenconnects to all of those nodes such that we have a complete network

    def outbound_node_connected(self, node):
        # When we connect to an outbound node
        self.connected((node.host, node.port))
        self._set_of_connections.add((node.host, node.port))
        print("outbound_node_connected (" + self.id + "): " + node.id)
        
    def inbound_node_connected(self, node):
        # When an inbound node connects to us

        print("inbound_node_connected: (" + self.id + "): " + node.id)

        # message = {"connections" : [(n.host, n.port) for n in self.all_nodes]}
        message = {"connections" : list(self._set_of_connections)}

        self.send_to_node(node, message)

        self._set_of_connections.add((node.host, node.port))

    def inbound_node_disconnected(self, node):
        print("inbound_node_disconnected: (" + self.id + "): " + node.id)

    def outbound_node_disconnected(self, node):
        print("outbound_node_disconnected: (" + self.id + "): " + node.id)

    def node_message(self, node, data):
        # When a node sends us a message
        if 'connections' not in data and 'submask' not in data:
            print("node_message (" + self.id + ") from " + node.id + ": " + str(data))

        if 'connections' in data:
            for host, port in data['connections']:
                if host != self.host or int(port) != self.port and (host, port) not in self.connected:
                    #print(f"Attempting to connect to node at {host} on port {port}")
                    self.connected.add((host, port))
                    self.connect_with_node(host, int(port))

        if 'poll' in data:
            # A node has requested to aggregate data
            print("POLL RECV", self.sent_sub_masks, self.received_sub_masks)
            requesting_node_id, requesting_node_host, requesting_node_port = data['poll']
            self._compute_submasks(requesting_node_id)
            # thread = threading.Thread(target=_await_all_submasks, args=(self, len(self.all_nodes) - 1))
            # thread.start()
            # thread.join()

            while len(self.received_sub_masks) != len(set([(node.host, node.port) for node in self.all_nodes])) - 1:
                time.sleep(0.01)

            # For testing to make sure we actually have all the proper masks
            assert len(self.sent_sub_masks) == len(self.received_sub_masks)

            # At this point, we have all of the sub_masks sent and received. Compute pertubations and send to requester.

            # print(self.id, self.sent_sub_masks)
            # print(self.id, self.received_sub_masks)
            self._send_masked_value(requesting_node_id, requesting_node_host, requesting_node_port)
            
        if 'submask' in data:
            self.received_sub_masks[node.id] = data['submask']

        if 'aggregation_value' in data:
            received_host, received_port, received_value = data['aggregation_value']
            self.received_aggragated_values[(received_host, received_port)] = received_value
    
    def _send_masked_value(self, id_to_send_to, host_to_send_to, port_to_send_to):
        #self.lock.acquire()
        mask = 0

        print(self.id, "SENT",self.sent_sub_masks)
        print(self.id, "RECEIVED", self.received_sub_masks)

        for recipient in self.sent_sub_masks:
            pair_pertubation = (self.sent_sub_masks[recipient] - self.received_sub_masks[recipient])

            # print(recipient, pair_pertubation, self.sent_sub_masks[recipient], self.received_sub_masks[recipient])
            
            mask += pair_pertubation % CRYPTOGRAPHIC_BASE

        # print(self.id, "MASK", mask)

        val_to_send = (self.value + mask) % CRYPTOGRAPHIC_BASE

        message = {"aggregation_value" : (self.host, self.port, val_to_send)}

        #self.lock.release()

        # To optimize this
        for node in self.all_nodes:
            # print(f"ID: {self.id}", node.host, node.port, host_to_send_to, port_to_send_to, type(node.host), type(node.port), type(host_to_send_to), type(port_to_send_to))
            if node.host == host_to_send_to and int(node.port) == int(port_to_send_to):
                self.send_to_node(node, message)


    def _compute_submasks(self, requesting_node):
        # We assume the network is fully connected
        #ipaddr, port = requesting_node
        #print(ipaddr, port)

        connected = set()

        for node in self.all_nodes:
            if node.id != requesting_node and node.id not in connected:
                submask = random.randint(0, CRYPTOGRAPHIC_BASE-1)
                message = {"submask" : submask}
                self.send_to_node(node, message)
                self.sent_sub_masks[node.id] = submask
                self.connected.add((node.host, node.port))

    def poll_peers(self):
        self.send_to_nodes({"poll" : (self.id, self.host, self.port)})

        # thread = threading.Thread(target=_await_all_requested_values, args=(self, len(self.all_nodes)))
        # thread.start()
        # thread.join()

        print(f"There are {len(self.all_nodes)} connected to node {self.id}")

        while len(self.received_aggragated_values) != len(set([(node.host, node.port) for node in self.all_nodes])):
            print(len(self.received_aggragated_values))
            time.sleep(2.01)

        #print(self.received_aggragated_values)

        return sum(self.received_aggragated_values.values()) % CRYPTOGRAPHIC_BASE

    def node_disconnect_with_outbound_node(self, node):
        print("node wants to disconnect with oher outbound node: (" + self.id + "): " + node.id)
        
    def node_request_to_stop(self):
        print("node is requested to stop (" + self.id + "): ")

def _await_all_submasks(peer, num_submasks_to_wait):
    # Blocks execution of the current thread until the current node has received all submasks
    while len(peer.received_sub_masks) != num_submasks_to_wait:
        time.sleep(0.01)

    return

def _await_all_requested_values(peer, num_values_to_collect):
    while len(peer.received_aggragated_values) != num_values_to_collect:
        time.sleep(0.01)

    return 



def main():
    node1 = SecAggPeer("127.0.0.1", 8889, 1, 10)
    node1.start()

    node2 = SecAggPeer("127.0.0.1", 8999, 2, 20, connect_to_addr="127.0.0.1", connect_to_port=8889)
    node2.start()

    node3 = SecAggPeer("127.0.0.1", 9999, 3, 30, connect_to_addr="127.0.0.1", connect_to_port=8889)
    node3.start()

    # node4 = SecAggPeer("127.0.0.1", 9998, 4, 40, connect_to_addr="127.0.0.1", connect_to_port=8889)
    # node4.start()

    time.sleep(5)

    print(node1.all_nodes)
    print(node2.all_nodes)
    print(node3.all_nodes)
    # print(node4.all_nodes)

    print(node3.poll_peers())

    # time.sleep(5)

    # print(node1.sent_sub_masks, node1.received_sub_masks)
    # print(node2.sent_sub_masks, node2.received_sub_masks)
    # print(node4.sent_sub_masks, node4.received_sub_masks)

if __name__ == "__main__":
    main()

# import sys
# import time
# sys.path.insert(0, '..') # Import the files where the modules are located

# node_1 = MyOwnPeer2PeerNode("127.0.0.1", 8999, 1)
# node_2 = MyOwnPeer2PeerNode("127.0.0.1", 8998, 2)
# node_3 = MyOwnPeer2PeerNode("127.0.0.1", 8997, 3)

# time.sleep(1)

# node_1.start()
# node_2.start()
# node_3.start()

# time.sleep(1)

# debug = False
# node_1.debug = debug
# node_2.debug = debug
# node_3.debug = debug


# node_1.connect_with_node('127.0.0.1', 8998)
# node_2.connect_with_node('127.0.0.1', 8997)
# node_3.connect_with_node('127.0.0.1', 8999)

# time.sleep(2)

# node_1.send_to_nodes("message: Hi there!")

# time.sleep(2)

# print("node 1 is stopping..")
# node_1.stop()

# time.sleep(20)

# node_2.send_to_nodes("message: Hi there node 2!")
# node_2.send_to_nodes("message: Hi there node 2!")
# node_2.send_to_nodes("message: Hi there node 2!")
# node_3.send_to_nodes("message: Hi there node 2!")
# node_3.send_to_nodes("message: Hi there node 2!")
# node_3.send_to_nodes("message: Hi there node 2!")

# time.sleep(10)

# time.sleep(5)

# node_1.stop()
# node_2.stop()
# node_3.stop()
# print('end test')