import os
from multiprocessing import Process
import signal
import sys

def get_filename(file):
    return os.path.splitext(os.path.basename(file))[0]

def multiprocessing_routine(queue, nproc, target_func):
    
    while queue.qsize() > 0:
        procs = []
        for _ in range(int(nproc)):
            if queue.qsize() > 0:
                args = queue.get()
                print("args")
                print(args)
                if isinstance(args, (list, tuple)):
                    p = Process(target=target_func, args=args)
                else:
                    p = Process(target=target_func, args=(args,))
                procs.append(p)
            else:
                break
        for p in procs:
            p.start()
        for p in procs:
            p.join()
