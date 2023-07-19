import threading
import random
import time

thread_lock = [True, True]


def print_thread_name(num, barrier):
    thread_name = threading.current_thread().name
    while True:
        wait_time = random.randint(1, 5)  # Random wait time between 1 and 5 seconds
        time.sleep(wait_time)
        barrier.wait()
        current_time = time.perf_counter()
        print("Thread", num, "waited for", wait_time, "seconds", "at time", current_time)


barrier = threading.Barrier(2)
# Create the first thread
thread1 = threading.Thread(target=print_thread_name, args=(0, barrier))

# Create the second thread
thread2 = threading.Thread(target=print_thread_name, args=(1, barrier))

# Start both threads
thread1.start()
thread2.start()

# Wait for both threads to finish
thread1.join()
thread2.join()

print("Main thread exiting")
