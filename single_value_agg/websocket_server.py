import asyncio
import websockets
import argparse
import json
import sys
import pickle
import copy

"""
Run this with parameter n for how many clients to accept before running the aggregation.

First, wait for all n clients to connect.

Next, each pair of users agree on a matched pair of input perturbations.

Then, each client sends their masked value to the server using all the perturbations.
"""

# (1) receive a public key from each client
# (2) once we receive all public keys, begin aggregation
#  - broadcast public keys to all clients
#  - receive messages from all n clients with their n perturbations
#  - send each client their appropriate set of perturbations from their peers
# (3) receive final values from each client
# (4) aggregate and broadcast


class SecureAggServer:
    def __init__(self, client_threshold, base):
        # wait for this many clients to connect before running protocol
        self.client_threshold = client_threshold
        self.connections = dict()  # maps hostname:port -> websocket connection
        self.pub_keys = dict()  # maps hostname:port -> public key

        self.base = base

        # nested dict: to_receive -> {perturbation_creator -> perturbation}
        self.perturbations = dict()

        self.num_perturbation_received = 0

        self.agg = 0
        self.received_value_count = 0

    async def handler(self, websocket):
        # Turn away new connections if we already have enough clients
        if len(self.connections) >= self.client_threshold:
            await websocket.send(pickle.dumps({"type": "message", "message": "Enough clients have already connected."}))
            return

        # Store new connection
        user_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        print(f"Received connection from client: {user_id}")
        self.connections[user_id] = websocket

        # Send the client the base for this session
        await websocket.send(pickle.dumps({"type": "init_base_param", "base": self.base}))

        # This big try block handles the client when it's connected, and the finally block
        # removes it from the connections dict when it disconnects.
        try:
            # For each message received over this socket
            async for m_raw in websocket:
                try:
                    # Try to unpickle the message
                    m = pickle.loads(m_raw)
                    message_type = m["type"]
                except (TypeError, ValueError, KeyError) as e:
                    print(f"Unable to decode message: {m_raw}")
                    print(f"Error: {e}")
                    continue

                if message_type == "public_key":
                    print(f"Received public key from client {user_id}")

                    # store the pub key
                    self.pub_keys[user_id] = m["public_key"]

                    # if this was the last one we needed, initialize perturbations dict with all client ids
                    # and broadcast all public keys
                    if len(self.pub_keys) == self.client_threshold:
                        for peer_id in self.pub_keys:
                            self.perturbations[peer_id] = dict()

                        print("Broadcasting public keys.")
                        await self.broadcast({"type": "public_key_broadcast", "public_keys": self.pub_keys})

                if message_type == "perturbations":
                    print(f"Received perturbations from client {user_id}")
                    self.num_perturbation_received += 1

                    for peer, perturbation_message in m["perturbations"].items():
                        self.perturbations[peer][user_id] = perturbation_message

                    # if we've received all perturbations, send each client their appropriate set of perturbations
                    if self.num_perturbation_received == self.client_threshold:
                        print("Received all perturbations.")
                        for peer_id, peer_generated_perturbations in self.perturbations.items():
                            await self.message_user(peer_id, pickle.dumps({"type": "perturbations", "perturbations": peer_generated_perturbations}))

                if message_type == "value":
                    print(f"Received value {m['value']} from client {user_id}")
                    self.agg += m['value']
                    self.received_value_count += 1

                    if self.received_value_count == self.client_threshold:
                        self.agg = self.agg % self.base
                        print(
                            f"✨🔐 SECURE AGGREGATION 🔐✨ \n✨🔐    Result: {self.agg}     🔐✨\n")
                        await self.broadcast({"type": "aggregation_result", "aggregation_result": self.agg})
                        print("Resetting server state.")
                        await self.close_connections_and_reset()
                        print("Ready for new session.\n", "*"*8, "\n")

            await websocket.wait_closed()

        finally:
            if user_id in self.connections:
                del self.connections[user_id]

    async def broadcast(self, unpickled_payload):
        message = pickle.dumps(unpickled_payload)
        websockets.broadcast(
            self.connections.values(), message)

    async def message_user(self, user_id, message):
        # raises KeyError if user disconnected
        websocket = self.connections[user_id]
        await websocket.send(message)  # may raise websockets.ConnectionClosed

    async def close_connections_and_reset(self):
        # have to make a copy since you can't modify the dict while iterating over it
        connections_to_close = copy.copy(list(self.connections.values()))

        for connection in connections_to_close:
            # note: closing connection also removes it from the dict thanks to the finally clause above
            await connection.close()

        self.connections = dict()
        self.pub_keys = dict()
        self.perturbations = dict()
        self.num_perturbation_received = 0
        self.agg = 0
        self.received_value_count = 0


async def main(client_threshold, base, host, port):
    server = SecureAggServer(client_threshold, base)
    async with websockets.serve(server.handler, host, port):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-n", "--num_clients",
                        help="Number of clients", type=int)
    parser.add_argument("-b", "--base",
                        help="Cryptographic base", type=int)
    parser.add_argument("-h", "--host",
                        help="Hostname", type=str)
    parser.add_argument("-p", "--port",
                        help="Port", type=int)

    args = parser.parse_args()

    if len(sys.argv) < 2:
        print(
            f"Usage: python3 websocket_server.py -n <num_clients> -b <cryptographic_base> -h <hostname> -p <port>")
        exit(1)

    if not args.host:
        args.host = "localhost"
    if not args.port:
        args.port = 8001

    print(
        f"Running server on {args.host}:{args.port} with client_threshold = {args.num_clients} ")
    asyncio.run(main(args.num_clients, args.base, args.host, args.port))
