from subprocess import Popen, PIPE
import logging
import os
import shlex
import time
from PyQt5.QtCore import QObject, pyqtSignal

logger = logging.getLogger('RosEM')

class MonitorJob(QObject):
    finished = pyqtSignal()
    update_log = pyqtSignal(tuple)
    clear_log = pyqtSignal(int)
    job_status = pyqtSignal(dict)

    def __init__(self, parent, job_params):
        super(MonitorJob, self).__init__()
        self._parent = parent
        self.job_params = job_params.copy()

        with self._parent.db.session_scope() as sess:
            self.sess = sess

    def run(self):

        current_job_id = self.job_params['job_id']
        logger.debug(f"In monitor thread for job id {current_job_id}")
        pointer = None

        self.clear_log.emit(0)

        while True:
            i = 0
            if not 'pid' in self.job_params:
                while not 'pid' in self._parent.job_params:
                    if i < 5:
                        time.sleep(1)
                        i += 1
                    else:
                        pid = None
                        logger.error("Pid not found after 5 retries")
                        break
                else:
                    pid = self._parent.job_params['pid']
            else:
                pid = self.job_params['pid']

            exit_code = self._parent.job.get_exit_code_from_log(self.job_params['log_file'])
            #logger.debug(f"Exit code is {exit_code}")
            job_status = self._parent.job.get_status(current_job_id, self.sess)
            if not job_status == 'aborted':
                if exit_code is None:
                    if self._parent.job.check_pid(pid):
                        #logger.debug("job pid found. job running")
                        i = 0
                        while i < 10:
                            if os.path.exists(self.job_params['log_file']):
                                with open(self.job_params['log_file'], 'r') as log:
                                    if not pointer is None:
                                        log.seek(pointer)
                                    lines = log.readlines()
                                    if not lines == []:
                                        self.update_log.emit((lines, current_job_id))
                                        pass
                                    if pointer is None:
                                        log.seek(0, 2)
                                    pointer = log.tell()
                                break
                            else:
                                time.sleep(1)
                                logger.debug("No log file found. Trying again in 1 sec.")
                                i += 1
                        else:
                            logger.error("No log file found after 10 retries.")
                            self.job_params['status'] = "error"
                            self._parent.job.update_status("error", self.job_params['job_id'], self.sess)
                            break
                    else:
                        logger.debug("pid not found")
                        self.job_params['status'] = "unknown"
                        self._parent.job.update_status("unknown", self.job_params['job_id'], self.sess)
                        break
                else:
                    logger.debug("exit code found")
                    if exit_code == 0:
                        self.job_params['status'] = "finished"
                        #self._parent.job.update_status("finished", self.job_params['job_id'])
                        
                    elif exit_code == 1:
                        self.job_params['status'] = "error"
                        #self._parent.job.update_status("error", self.job_params['job_id'])
                    elif exit_code == 2:
                        self.job_params['status'] = "aborted"
                        #self._parent.job.update_status("aborted", self.job_params['job_id'])

                    break
            else:
                self.job_params['status'] = "aborted"
                break

        logger.debug("Job finished. emitting signals from monitor thread")
        self.job_status.emit(self.job_params)



class RunProcessThread(QObject):
    finished = pyqtSignal()
    job_status = pyqtSignal(dict)
    change_tab = pyqtSignal()

    def __init__(self, parent, job_params):
        super(RunProcessThread, self).__init__()
        self._parent = parent
        self.job_params = job_params.copy()

        with self._parent.db.session_scope() as sess:
            self.sess = sess

    def run(self):
        #self._parent.validation_panel.Enable(False)
        #self._parent.validation_panel.Hide()

        try:
            #basedir = os.getcwd()
            os.chdir(self.job_params['job_path'])
        except:
            logger.error('Job directory not accessible!')
        logger.debug("Starting job")
        logger.debug(self.job_params)
        cmd = self._parent.job.prepare_cmd(self.job_params)
        #pid = os.fork()
        #if pid == 0:

        #cpid = os.getpid()
        #ppid = os.getppid()
        cmd = ' '.join(cmd)
        logger.debug("Starting with command\n{}".format(cmd))
        with open("run.sh", 'w') as f:
            f.write(cmd)
        cmd = shlex.split(cmd, posix=False)
        logger.debug("Starting with command\n{}".format(cmd))
        logger.debug("job params")
        logger.debug(cmd)
        p = Popen(cmd, preexec_fn=os.setsid)
        cpid = os.getpgid(p.pid)
        logger.debug("PID of child is {}".format(cpid))
        self.job_params['status'] = "running"
        self.job_params['pid'] = cpid
        self._parent.job.update_pid(cpid, self.job_params['job_id'], self.sess)
        self.job_params['pid'] = cpid

        logger.debug("Job finished. emitting signals from run process thread")
        self.job_status.emit(self.job_params)
        self.change_tab.emit()
