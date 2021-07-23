#Copyright 2021 Georg Kempf, Friedrich Miescher Institute for Biomedical Research
#
#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at
#
#http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.
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
