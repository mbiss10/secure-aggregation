import asyncio
import websockets
import argparse
import json
import sys
import copy


class DemoSecureAggServer:
    def __init__(self, client_threshold, base):

        # wait for this many clients to connect before running protocol
        self.client_threshold = client_threshold
        self.connections = dict()  # maps ids (hostname:port) -> websocket connection
        self.base = base

        self.ready_set_lock = asyncio.Lock()
        self.ready_set = set()  # set of ids that have submitted a value

        # nested dict: to_receive -> {perturbation_creator -> perturbation}
        self.perturbations = dict()
        self.num_perturbation_received = 0

        self.agg = 0
        self.received_value_count = 0

    async def handler(self, websocket):
        # Turn away new connections if we already have enough clients participating
        if len(self.ready_set) >= self.client_threshold:
            await websocket.send(json.dumps({"type": "message", "message": "Enough clients have already joined."}))
            return

        # Store new connection
        user_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        print(f"Received connection from client: {user_id}")
        self.connections[user_id] = websocket

        # Send the client the base for this session
        print(f"\tSending base parameter to new client...")
        await websocket.send(json.dumps({"type": "init_base_param", "base": self.base}))

        # Send client it's ID since we can't get this from JS code
        print(f"\tInforming client of its own userid...")
        await websocket.send(json.dumps({"type": "your_id", "id": user_id}))

        # This big try block handles the client when it's connected, and the finally block
        # removes it from the connections dict when it disconnects.
        try:
            # For each message received over this socket
            async for m_raw in websocket:
                try:
                    # Try to load the message
                    m = json.loads(m_raw)
                    message_type = m["type"]
                except (TypeError, ValueError, KeyError) as e:
                    print(f"Unable to decode message: {m_raw}")
                    print(f"Error: {e}")
                    continue

                if message_type == "ready":
                    print(f"Client {user_id}: READY!")

                    async with self.ready_set_lock:
                        if len(self.ready_set) < self.client_threshold:
                            self.ready_set.add(user_id)

                        # if this was the last ready we needed, initialize perturbations dict with all client ids
                        # and broadcast all user ids
                        if len(self.ready_set) == self.client_threshold:
                            for peer_id in self.ready_set:
                                self.perturbations[peer_id] = dict()

                            print(
                                "\nRound 1 complete! Received all user_ids. Broadcasting ids...\n")
                            await self.broadcast({"type": "user_id_broadcast", "user_ids": list(self.ready_set)})

                if message_type == "perturbations":
                    print(f"Received perturbations from client: {user_id}")
                    self.num_perturbation_received += 1

                    for peer, perturbation_message in m["perturbations"].items():
                        self.perturbations[peer][user_id] = perturbation_message

                    # if we've received all perturbations, send each client their appropriate set of perturbations
                    if self.num_perturbation_received == self.client_threshold:
                        print(
                            "\nRound 2 complete! Received all perturbations. Distributing them to clients...\n")
                        for peer_id, peer_generated_perturbations in self.perturbations.items():
                            await self.message_user(peer_id, json.dumps({"type": "perturbations", "perturbations": peer_generated_perturbations}))

                if message_type == "value":
                    print(
                        f"Received masked value {m['value']} from client: {user_id}")
                    self.agg += m['value']
                    self.received_value_count += 1

                    if self.received_value_count == self.client_threshold:
                        self.agg = self.agg % self.base
                        print(
                            f"\n✨🔐 SECURE AGGREGATION 🔐✨ \n✨🔐    Result: {self.agg}     🔐✨\n")
                        await self.broadcast({"type": "aggregation_result", "aggregation_result": self.agg})
                        print("Resetting server state.")
                        await self.close_connections_and_reset()
                        print("Ready for new session.\n", "*"*8, "\n")

            await websocket.wait_closed()

        finally:
            if user_id in self.connections:
                del self.connections[user_id]
            if user_id in self.ready_set:
                print(
                    f"Client {user_id} disconnected (was part of READY set).")
                self.ready_set.remove(user_id)

    async def broadcast(self, payload):
        message = json.dumps(payload)
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
    server = DemoSecureAggServer(client_threshold, base)
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

    if not args.num_clients or not args.base:
        print(
            f"Usage: python3 websocket_server.py -n <num_clients> -b <cryptographic_base> -h <hostname> -p <port>")
        exit(1)

    if not args.host:
        args.host = "localhost"
    if not args.port:
        args.port = 8001

    print(
        f"Running server on {args.host}:{args.port} with client_threshold = {args.num_clients}")
    asyncio.run(main(args.num_clients, args.base, args.host, args.port))
