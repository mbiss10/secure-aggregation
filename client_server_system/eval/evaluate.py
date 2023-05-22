import threading
from queue import Queue
import asyncio
import time
import csv
import random
import numpy as np
import sys
import os

# setting path
sys.path.append('../')
sys.path.append('../../')
from client_server_system.websocket_client_vector import main


HOST = "137.165.8.13" # limia   # "localhost"
PORT = 8891

CLIENT_COUNT = 8
NUM_VALUES = [2, 50] + list(range(100, 500, 100)) + list(range(500, 5000, 500)) + list(range(5000, 10000, 1000))
if __name__ == "__main__":

    with open("./eval/results/local_client_results_w_limia_serving_num_values.csv", 'w') as f:
        writer = csv.writer(f, delimiter=',')
        writer.writerow(["num_values", "executionTime",
                            "all_return_vals_the_same", "expected_value==return_val"])
        
        for value_count in NUM_VALUES:
            rand_values = [[random.randint(0, 1000000) for _ in range(
                value_count)] for _ in range(CLIENT_COUNT)]
            matrix = np.array(rand_values)
            expected_sum_arr = np.sum(matrix, axis=0)

            startTime = time.time()

            threads = []
            return_vals = list()
            for thread_idx in range(CLIENT_COUNT):
                t = threading.Thread(target=lambda l, arg1: l.append(
                    asyncio.run(arg1)), args=(return_vals, main(rand_values[thread_idx], HOST, PORT),))
                threads.append(t)
                t.start()

            for thread in threads:
                thread.join()

            executionTime = (time.time() - startTime)

            return_vals = np.array(return_vals)
            all_return_vals_the_same = (return_vals == return_vals[0]).all()
            if not all_return_vals_the_same:
                for row in matrix:
                    if row != matrix[0]:
                        print("HERE")
                        print(row)
                        print(matrix[0])
                        exit(1)
            return_val = return_vals[0]
            expected_value = expected_sum_arr.tolist()

            writer = csv.writer(f, delimiter=',')
            writer.writerow([value_count, executionTime,
                            all_return_vals_the_same, expected_value==return_val])
