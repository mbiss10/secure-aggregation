import asyncio
import time
import sys
import json
import websockets
import argparse
import random
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from Crypto.Cipher import AES, PKCS1_OAEP
import pickle
import threading


"""

Note: conveniently, since the server and the clients are somewhat cooperative (insofar as 
the server wants all the clients to be able to run the protocol successfully enough that 
the aggregation is actually correct), we don't need to wory about *data* integrity/authenticity
when clients encrypt their perturbations and send them amongst each other using the server
as a middleman. We only care about confidentiality. In other words, the server shouldn't be able
to read the data being sent, but we don't have to worry about it tampering with the values.

^ This may be moot though b/c the library we're using seems to do both at the same time.

"""


class SecureAggClient:
    def __init__(self, value, connection):
        self.base = None

        self.rsa_keys = RSA.generate(2048)
        self.priv_key = self.rsa_keys.export_key()
        self.pub_key = self.rsa_keys.publickey().export_key()

        self.peer_perturbations = {}
        self.perturbation_messages = {}
        self.connection = connection
        self.id = f"{connection.local_address[0]}:{connection.local_address[1]}"
        self.value = value

    def set_base(self, base: int):
        self.base = base

    def create_perturbation_messages(self, public_key_dict):
        assert self.base is not None, "Base must be set before creating perturbations."

        for peer, peer_pub_key_str in public_key_dict.items():
            if peer == self.id:
                continue

            # Generate random value for this peer and prep it for encryption
            peer_perturb_val = random.randint(0, self.base-1)
            data = str(peer_perturb_val).encode("utf-8")

            # Store the unencrypted perturbation value for this client to use when computing
            # the value to send to the server
            self.peer_perturbations[peer] = peer_perturb_val

            # Use an AES session key so that we can encrypt arbitrarily large data.
            # If we only used RSA, we'd be limited to the size of the key.
            session_key = get_random_bytes(16)

            # Encrypt the session key with the peer's public RSA key.
            # Note that we're sending public keys as strings generated by the export_key
            # method, so we need to convert them back to RSA objects.
            peer_pub_key = RSA.import_key(peer_pub_key_str)
            cipher_rsa = PKCS1_OAEP.new(peer_pub_key)
            enc_session_key = cipher_rsa.encrypt(session_key)

            # Encrypt the data with the AES session key
            cipher_aes = AES.new(session_key, AES.MODE_EAX)
            ciphertext, tag = cipher_aes.encrypt_and_digest(data)

            # Store the message that will be sent to the peer
            self.perturbation_messages[peer] = (
                enc_session_key, cipher_aes.nonce, tag, ciphertext)

    async def send_perturbations(self):
        await self.connection.send(pickle.dumps({"type": "perturbations", "perturbations": self.perturbation_messages}))

    def compute_value(self, received_peer_perturbations):
        to_send = 0
        for peer, peer_perturb_message in received_peer_perturbations.items():
            if peer == self.id:
                continue
            else:
                # Decrypt the peer's message
                enc_session_key, nonce, tag, ciphertext = peer_perturb_message
                # First, decrypt the session key with the private RSA key
                cipher_rsa = PKCS1_OAEP.new(self.rsa_keys)
                session_key = cipher_rsa.decrypt(enc_session_key)
                # Then, decrypt the data with the AES session key
                cipher_aes = AES.new(session_key, AES.MODE_EAX, nonce)
                raw_data = cipher_aes.decrypt_and_verify(ciphertext, tag)
                try:
                    received_perturb_val = int(raw_data.decode("utf-8"))
                except ValueError:
                    print("Unable to decode recieved message. It may not be an int.")

                s_uv = self.peer_perturbations[peer]
                s_vu = received_perturb_val
                p_uv = (s_uv - s_vu) % self.base
                to_send += p_uv

        return (to_send + self.value) % self.base

    async def send_val(self, to_send):
        message = pickle.dumps(
            {"type": "value", "value": to_send})
        await self.connection.send(message)


async def main(value, host, port):

    async with websockets.connect(f"ws://{host}:{port}") as websocket:
        client = SecureAggClient(value, websocket)
        print(f"I am Client [{client.id}]. Successfully connected to server.")

        await websocket.send(pickle.dumps({"type": "public_key", "public_key": client.pub_key}))

        async for m_raw in websocket:
            try:
                m = pickle.loads(m_raw)
                print(f"Received message of type: {m['type']}")
                message_type = m["type"]
            except (TypeError, ValueError, KeyError) as e:
                print(f"Error: {e}")
                continue

            if message_type == 'public_key_broadcast':
                # create perturbations and send to all peers
                client.create_perturbation_messages(m['public_keys'])
                await client.send_perturbations()

            elif message_type == 'init_base_param':
                print(f"Received base parameter from server: {m['base']}")
                client.set_base(m['base'])

            elif message_type == 'perturbations':
                to_send = client.compute_value(m["perturbations"])
                await client.send_val(to_send)

            elif message_type == 'aggregation_result':
                print(f"Final aggregation result 😎: {m['aggregation_result']}")
                return m['aggregation_result']

            elif message_type == 'message':
                print(f"Received message: {m['message']}")

            else:
                print(f"Received unknown message type: {message_type}")

        print("Connection closed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-v", "--value",
                        help="This client's value", type=int)
    parser.add_argument("-h", "--host",
                        help="Hostname", type=int)
    parser.add_argument("-p", "--port",
                        help="Port", type=int)
    args = parser.parse_args()

    if len(sys.argv) < 1:
        print(
            f"Usage: python3 websocket_client.py -v <client_value")
        exit(1)

    if not args.host:
        args.host = "localhost"
    if not args.port:
        args.port = 8001

    asyncio.run(main(args.value, args.host, args.port))
