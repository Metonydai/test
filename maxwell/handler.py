# -*- coding: utf-8 -*-
import json
import os
import psutil
import subprocess
import requests
import time
from pathlib import Path
from data_access import get_config
from data_access.logger import LoggerManager

# =============================================================================
# cmd
# =============================================================================
CMD_PYTHON = "python"
TASKKILL_PID_FMT = "taskkill /pid %s -t -f"

FLASK_WORKER_PATH = str(Path(__file__).parent / 'FlaskService.py')
CORE_GEN_SERVICE_PATH = str(Path(__file__).parent / 'CoreGen.py')
CORE_WINDING_GEN_SERVICE_PATH = str(Path(__file__).parent / 'CoreWindingGen.py')
TASK_FILE_MAPPING = {'core_gen':CORE_GEN_SERVICE_PATH, 'core_winding_gen': CORE_WINDING_GEN_SERVICE_PATH}

RMQ_WORKER_PATH = str(Path(__file__).parent / 'rabbitq_worker.py')

WORKER_DURATION, WORKER_CNT = get_config.get_controller()
FREECAD_PYTHON_ENV = get_config.get_freecad_python_env()
FLASK_PORT = get_config.get_flask_port()

DEV_FOLDER_PATH = Path(get_config.get_dev_folder_path())
STAGE_FOLDER_PATH = Path(get_config.get_stage_folder_path())
PROD_FOLDER_PATH = Path(get_config.get_prod_folder_path())
# =============================================================================
# FLASK
# =============================================================================
LOG = LoggerManager().getlog()

### Start Flask
def start_flask_worker() -> int:
    cmd = subprocess.Popen([CMD_PYTHON, FLASK_WORKER_PATH], shell=True)
    return cmd.pid

### Start RabbitMQ
def start_rmq_worker() -> tuple[int, int, int]:
    cmd = subprocess.Popen([CMD_PYTHON, RMQ_WORKER_PATH], shell=True)
    return cmd.pid

### Check Flask
def check_flask_pid_status(flask_pid) -> int:
    if (psutil.pid_exists(flask_pid)):
        pid_state = psutil.Process(flask_pid).status()
        if (pid_state == 'running'):
            log_msg = f"Normal Execution FLASK PID: {flask_pid}"
            LOG.info('(%s) %s', __name__, log_msg , extra={'correlationId': '['+ 'NULL'+']'})
            print("Normal Execution FLASK PID:", flask_pid)
        else:
            os.system(TASKKILL_PID_FMT % str(flask_pid))
            log_msg = f"Error Execution and Kill FLASK PID: {flask_pid}"
            LOG.error('(%s) %s', __name__, log_msg , extra={'correlationId': '['+ 'NULL'+']'})
            print("Error Execution and Kill FLASK PID:", flask_pid)
            flask_pid = start_flask_worker()
    else:
        flask_pid = start_flask_worker()
    return flask_pid

def check_rmq_pid_status(rmq_pid) -> int:
    if (psutil.pid_exists(rmq_pid)):
        pid_state = psutil.Process(rmq_pid).status()
        if (pid_state == 'running'):
            log_msg = f"Normal Execution RabbitMQ PID: {rmq_pid}"
            LOG.info('(%s) %s', __name__, log_msg , extra={'correlationId': '['+ 'NULL'+']'})
            print("Normal Execution RabbitMQ PID:", rmq_pid)
        else:
            os.system(TASKKILL_PID_FMT % str(rmq_pid))
            log_msg = f"Error Execution and Kill RabbitMQ PID: {rmq_pid}"
            LOG.error('(%s) %s', __name__, log_msg , extra={'correlationId': '['+ 'NULL'+']'})
            print("Error Execution and Kill RabbitMQ PID:", rmq_pid)
            rmq_pid = start_rmq_worker()
    else:
        rmq_pid = start_rmq_worker()
    return rmq_pid

def check_fc_pid_status(pid_dict, worker_duration, service) -> dict:
    if len(pid_dict) == 0:
        return {}

    # check all pid in pid_dict
    try:
        for child_pid in pid_dict.keys():
            memory = 0
            if (psutil.pid_exists(child_pid)):
                pid_state = psutil.Process(child_pid).status()
                current_process = psutil.Process(child_pid)
                children_process = current_process.children(recursive=True)

                if (pid_state == 'running') and (time.time() - pid_dict[child_pid] < worker_duration):
                    log_msg = f"Normal Execution FREECAD WORKER PID: {child_pid}"
                    LOG.info('(%s) %s', __name__, log_msg , extra={'correlationId': '['+ 'NULL'+']'})
                    print("Normal Execution FREECAD WORKER PID:", child_pid)
                else:
                    os.system(TASKKILL_PID_FMT % str(child_pid))
                    log_msg = f"Error Execution and Kill FREECAD WORKER PID: {child_pid}"
                    LOG.error('(%s) %s', __name__, log_msg , extra={'correlationId': '['+ 'NULL'+']'})
                    print("Error Execution and Kill FREECAD WORKER PID:", child_pid)
                    pid_dict.pop(child_pid)
                    # Create a new worker and upadate to pid_dict
                    pid_dict.update(exe_popen(TASK_FILE_MAPPING[service]))

                # check memory usage ( > 2GB)
                for child in children_process:
                    memory += (psutil.Process(child.pid).memory_info().rss / 1024 ** 3)

                print("[Memory usage] " + str(memory) + " GB")
                log_msg = "[Memory usage] " + str(memory) + " GB"
                LOG.info('(%s) %s', __name__, log_msg , extra={'correlationId': '['+ 'NULL'+']'})
                if memory > 2:
                    print("Memory Exceed and Kill FREECAD WORKER PID:", child_pid)
                    log_msg = f"Memory Exceed and Kill FREECAD WORKER PID: {child_pid}"
                    LOG.info('(%s) %s', __name__, log_msg , extra={'correlationId': '['+ 'NULL'+']'})
                    os.system(TASKKILL_PID_FMT % str(child_pid))
                    pid_dict.pop(child_pid)
                    # Create a new worker and upadate to pid_dict
                    pid_dict.update(exe_popen(TASK_FILE_MAPPING[service]))
            else:
                print(f"FREECAD WORKER PID: {child_pid} DOES NOT EXIST, AND KILL THIS WORKER!", )
                log_msg = f"FREECAD WORKER PID: {child_pid} DOES NOT EXIST, AND KILL THIS WORKER!"
                LOG.info('(%s) %s', __name__, log_msg , extra={'correlationId': '['+ 'NULL'+']'})
                os.system(TASKKILL_PID_FMT % str(child_pid))
                pid_dict.pop(child_pid)
                # Create a new worker and upadate to pid_dict
                pid_dict.update(exe_popen(TASK_FILE_MAPPING[service]))
        # Keep Worker headcount
        if len(pid_dict) < WORKER_CNT:
            for _ in range(WORKER_CNT- len(pid_dict)):
                pid_dict.update(exe_popen(TASK_FILE_MAPPING[service]))
                log_msg = f"ADD FREECAD WORKER"
                LOG.info('(%s) %s', __name__, log_msg , extra={'correlationId': '['+ 'NULL'+']'})
            
    except:
        pass

    return pid_dict

def exe_popen(service_name) -> dict:
    cmd = subprocess.Popen([CMD_PYTHON, service_name], shell=True, cwd=FREECAD_PYTHON_ENV)
    return {
        cmd.pid: time.time()
    }

def check_core_gen_task_cnt() -> int:
    try:
        response = requests.get('http://127.0.0.1:'+str(FLASK_PORT)+'/get_core_queue_cnt')
        current_request_dic = json.loads(response.text)
        return int(current_request_dic['q_size'])
    except:
        return 0

def check_core_winding_gen_task_cnt() -> int:
    try:
        response = requests.get('http://127.0.0.1:'+str(FLASK_PORT)+'/get_core_winding_queue_cnt')
        current_request_dic = json.loads(response.text)
        return int(current_request_dic['q_size'])
    except:
        return 0

def get_task_count() -> dict:
    return {
        'core_gen': check_core_gen_task_cnt(),
        'core_winding_gen': check_core_winding_gen_task_cnt()
    }


if __name__ == '__main__':
    # initial flask API
    flask_pid = start_flask_worker()

    # initial RabbitMQ worker
    rmq_pid = start_rmq_worker()

    glb_core_pid_dict = {}
    glb_core_winding_pid_dict = {}
    while True:
        flask_pid = check_flask_pid_status(flask_pid)
        rmq_pid = check_flask_pid_status(rmq_pid)
        glb_core_pid_dict = check_fc_pid_status(glb_core_pid_dict, WORKER_DURATION, 'core_gen')
        glb_core_winding_pid_dict = check_fc_pid_status(glb_core_winding_pid_dict, WORKER_DURATION, 'core_winding_gen')
        
        task_cnt_dict = get_task_count()
        print("TASK CNT",task_cnt_dict)

        # if all_process_cnt < WORKER_CNT:
        if len(glb_core_pid_dict) == 0 and task_cnt_dict['core_gen'] > 0:
            # Arrange WORKER_CNT workers to work 
            for _ in range(WORKER_CNT):
                glb_core_pid_dict.update(exe_popen(TASK_FILE_MAPPING['core_gen']))

        if len(glb_core_winding_pid_dict) == 0 and task_cnt_dict['core_winding_gen'] > 0:
            # Arrange WORKER_CNT workers to work 
            for _ in range(WORKER_CNT):
                glb_core_winding_pid_dict.update(exe_popen(TASK_FILE_MAPPING['core_winding_gen']))

        time.sleep(3)
