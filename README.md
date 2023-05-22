# 🔐 Secure Aggregation for Federated Computation 😎

Demo (single value aggregation using fancy web app): https://youtu.be/52QeF3Di9nU  
Demo (vector aggregation running in the Terminal): https://youtu.be/Dxwz8Hh0N-M

#### Requirements
- `websockets` (which depends on / heavily leverages `asyncio`)
- `argparse`

#### Server
To run the protocol for vector aggregation, cd into the `client_server_system` directory and run `python3 websocket_server_vector.py`. By default, the server will run with the following parameters, although flags can be used to run the server with other settings:           
- b=1000000 (this is the `cryptographic_base` is a number that is used for modular arithmetic in cryptographic calculations within both the client and server programs. Note that this should be a huge number — greater than the expected sum of all client values — since the aggregate of all clients' values will be computed modulo this value.)
- 2 clients
- host=localhost
- port=8001
- client vectors include 5 values

#### Client
To run the protocol for vector aggregation, cd into the `client_server_system` directory and run `python3 websocket_client_vector.py -v {values}` where `{values}` is a comma-separated list of positive integers (e.g. `1,2,4,10,35`).

Once you've started a number of client programs equal to `num_clients`, the protocol will run and the server will print the aggregated sum.
