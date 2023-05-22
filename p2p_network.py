import time
from p2p_client import SecAggPeer

import random
import typing

from pprint import pprint

class Network():
    def __init__(self, num_nodes, base_port):
        base_node = SecAggPeer("127.0.0.1", base_port, id = 0, value = 0)
        base_node.start()

        self.nodes =[base_node]

        for i in range(num_nodes - 1):
            peer = SecAggPeer("127.0.0.1", base_port + 1 + i, id = i+1, value = (i + 1), connect_to_addr=base_node.host, connect_to_port=base_node.port)
            peer.start()

            self.nodes += [peer]

        time.sleep(5)

        for node in self.nodes:
            print(node.id, len(node.all_nodes), len(node.nodes_inbound), len(node.nodes_outbound), len(set([(node.host, node.port) for node in self.nodes])))
            #pprint(node.nodes_outbound)


    def close(self):
        for node in self.nodes:
            node.stop()

    def poll_peers(self):
        return self.nodes[0].poll_peers()
        #return random.choice(self.nodes).poll_peers()

def main():
    network = Network(100, 9999)

    time.sleep(10)
    
    print(network.poll_peers())

    network.close()

if __name__ == "__main__":
    main()
