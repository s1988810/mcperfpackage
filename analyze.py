import ast
import copy
import csv
import os
import re
from socket import IPV6_CHECKSUM
import statistics
import sys
from time import clock_settime
#import matplotlib.pyplot as plt
#import matplotlib.backends.backend_pdf
def derive_datatype(datastr):
    try:
        return type(ast.literal_eval(datastr))
    except:
        return type("")

def system_conf_fullname(system_conf):
    l = [
        'turbo={}'.format(system_conf['turbo']),
        'kernelconfig={}'.format(system_conf['kernelconfig']),
        'hyperthreading={}'.format(system_conf['ht']),
        #'idlegovernor={}'.format(system_conf['idlegovernor']),
        #'tickless={}'.format(system_conf['tickless']),
    ]
    if 'freq' in system_conf:
        l.append('freq={}'.format(system_conf['freq']))
    return '-'.join(l) + '-'

def system_conf_shortname(system_conf):
    short_kernelconfig = {
        'baseline': 'baseline',
        'disable_cstates': 'no_cstates',
        'disable_c6': 'no_c6',
        'disable_c1e_c6': 'no_c1e_c6',
        'quick_c1': 'q_c1',
        'quick_c1_c1e': 'q_c1_c1e',
        'quick_c1_disable_c6': 'q_c1-no_c6',
    }
    l = [
        'T' if system_conf['turbo'] else 'NT',
        short_kernelconfig[system_conf['kernelconfig']],
    ]
    if 'freq' in system_conf:
        l.append('F{}'.format(system_conf['freq']))
    return '-'.join(l) + '-'

def shortname(qps=None):
    return 'qps={}'.format(qps)

def parse_mcperf_stats(mcperf_results_path):
    stats = None
    with open(mcperf_results_path, 'r') as f:
        stats = {}
        for l in f:
            if l.startswith('#type'):
                stat_names = l.split()[1:]
                read_stats = next(f).split()[1:]
                update_stats = next(f).split()[1:]
                read_stats_dict = {}
                update_stats_dict = {}
                for i, stat_name in enumerate(stat_names):
                    read_stats_dict[stat_name] = float(read_stats[i])
                    update_stats_dict[stat_name] = float(update_stats[i])
                stats['read'] = read_stats_dict
                stats['update'] = update_stats_dict
            if l.startswith('Total QPS'):
                stats['total_qps'] = float(l.split()[3])
    return stats

def read_timeseries(filepath):
    header = None
    timeseries = None
    with open(filepath, 'r') as f:
        header = f.readline().strip()
       
        timeseries = []
        data = f.readline().strip().split(',')
        datatype = derive_datatype(data[1])
        f.seek(0)
        for l in f.readlines()[1:]:
            data = l.strip().split(',')
            timestamp = int(data[0])
            value = datatype(data[1].replace('.',''))
            
            timeseries.append((timestamp, value))
    return (header, timeseries)            

def read_timeseries_perf(filepath):
    header = None
    timeseries = None
    with open(filepath, 'r') as f:
        
        header = f.readline().strip().replace('.','_')
        header = header.replace(' ','_')
        timeseries = []
        data = f.readline().strip().split(',')
        
        datatype = derive_datatype(data[1])
        f.seek(0)
        for l in f.readlines()[1:]:
            data = l.strip().split(',')
            timestamp = int(data[0])
            value = datatype(data[1])
            timeseries.append((timestamp, value))
    return (header, timeseries)          
    

def add_metric_to_dict(stats_dict, metric_name, metric_value):
    head = metric_name.split('.')[0]
    tail = metric_name.split('.')[1:]
    if tail:
        stats_dict = stats_dict.setdefault(head, {})
        add_metric_to_dict(stats_dict, '.'.join(tail), metric_value)
    else:
        stats_dict[head] = metric_value

def parse_cstate_stats(stats_dir):
    stats = {}
    prog = re.compile('(.*)\.(.*)\.(.*)')
    for f in os.listdir(stats_dir):
        m = prog.match(f)
        if m and "CPU" in f:
            stats_file = os.path.join(stats_dir, f)
            cpu_id = m.group(1)
            state_name = m.group(2)
            metric_name = m.group(3)
            (metric_name, timeseries) = read_timeseries(stats_file)
            add_metric_to_dict(stats, metric_name, timeseries)
    
    return stats

def parse_perf_stats(stats_dir):
    stats = {}
    prog = re.compile('(.*)\.(.*)\.(.*)')
    for f in os.listdir(stats_dir):
        m = prog.match(f)
        if not m or not "CPU" in f:
            if not "package-0" in f and not "package-1" in f and not "dram" in f:
                stats_file = os.path.join(stats_dir, f)
                (metric_name, timeseries) = read_timeseries_perf(stats_file)
                
               
                add_metric_to_dict(stats, metric_name, timeseries)
    return stats
    
def parse_pkgcstate_stats(stats_dir):
    stats={}
    prog = re.compile('(.*)\.(.*)\.(.*)')
    for f in os.listdir(stats_dir):
        m = prog.match(f)
        if m:
            stats_file = os.path.join(stats_dir, f)
            cpu_id = m.group(1)
            state_name = m.group(2)
            metric_name = m.group(3)
            (metric_name, timeseries) = read_timeseries(stats_file)
            add_metric_to_dict(stats, metric_name, timeseries)

def parse_util_stats(util_stats_dirs):
    
    stats={}
    f="cpu_util"
    stats_file = os.path.join(util_stats_dirs, f)
    (metric_name, timeseries) = read_timeseries(stats_file)
    add_metric_to_dict(stats, metric_name, timeseries)
    return stats
    
def parse_rapl_stats(rapl_stats_file):
    stats = {}
    counter=0
    stats['package-0'] = []
    stats['package-1'] = []
    stats['dram'] = []
    package_0=0
    package_1=0
    dram=0
   
    package_0_stats_file = os.path.join(rapl_stats_file,'package-0')
    
    with open(package_0_stats_file, 'r') as f:
        metric,series = read_timeseries(package_0_stats_file)
        package_0=(series[1][1] - series[0][1])/((series[1][0]-series[0][0]))/1000000
        stats['package-0'].append(float(package_0))
    
    package_1_stats_file = os.path.join(rapl_stats_file,'package-1')
    with open(package_1_stats_file, 'r') as f:
        metric,series = read_timeseries(package_1_stats_file)
        package_1=(series[1][1] - series[0][1])/((series[1][0]-series[0][0]))/1000000
        stats['package-1'].append(float(package_1))
    
    dram_stats_file = os.path.join(rapl_stats_file,'dram')
    with open(dram_stats_file, 'r') as f:
        metric,series = read_timeseries(dram_stats_file)
        dram=(series[1][1] - series[0][1])/((series[1][0]-series[0][0]))/1000000
        stats['dram'].append(float(dram))
            
    return stats

def parse_server_side_stats(stats_dir):
    
    stats = {}
    stats['rusage_user'] = []
    stats['rusage_system'] = []
    warmup_stats_file = os.path.join(stats_dir,'memcachedstatswarmup')
    with open(warmup_stats_file, 'r') as f:
        for line in f:
            if "rusage_user" in line:
                rusage_user_warmup = line.split()[2]
            if "rusage_system" in line:
                rusage_system_warmup = line.split()[2]
       
    run_stats_file = os.path.join(stats_dir,'memcachedstatsrun')
    with open(run_stats_file, 'r') as f:
        for line in f:
            if "rusage_user" in line:
                rusage_user_run = line.split()[2]
            if "rusage_system" in line:
                rusage_system_run = line.split()[2]
                
    rusage_system = float(rusage_system_run) - float(rusage_system_warmup)
    rusage_user = float(rusage_user_run) - float(rusage_user_warmup)
        
    stats['rusage_user'].append(float(rusage_user))
    stats['rusage_system'].append(float(rusage_system))

    return stats
    
def parse_pcie_upi_stats(stats_dir):
    stats = {}
    prog = re.compile('(_*)\.')
    
    for f in os.listdir(stats_dir):
        m = prog.match(f)
        if not m:
            if not "package-0" in f and not "package-1" in f and not "dram" in f:
            
                stats_file = os.path.join(stats_dir, f)
                (metric_name, timeseries) = read_timeseries(stats_file)
                add_metric_to_dict(stats, metric_name, timeseries)
    
    return stats




def parse_single_instance_stats(stats_dir):
    stats = {}
    
    #rapl_stats_file = os.path.join(stats_dir,'memcached')
    #server_rapl_stats = parse_rapl_stats(rapl_stats_file)
    #util_stats_dir = os.path.join(stats_dir, 'memcached')
    #server_util_stats = parse_util_stats(util_stats_dir)
    server_stats_dir = os.path.join(stats_dir, 'memcached')
    #server_cstate_stats = parse_cstate_stats(server_stats_dir)
    server_perf_stats = parse_perf_stats(server_stats_dir)
    #server_latency_stats = parse_server_side_stats(stats_dir)
    #pcie_upi_stats_file = os.path.join(stats_dir,'memcached')
    #server_pcie_upi_stats = parse_pcie_upi_stats(pcie_upi_stats_file)
    
    stats['server'] = {**server_perf_stats}
    #mcperf_stats_file = os.path.join(stats_dir, 'mcperf')
    #stats['mcperf'] = parse_mcperf_stats(mcperf_stats_file)
    return stats

def parse_multiple_instances_stats(stats_dir, pattern='.*'):
    stats = {}
    for f in os.listdir(stats_dir):
        instance_dir = os.path.join(stats_dir, f)
        instance_name = f[:f.rfind('-')]
        stats.setdefault(instance_name, []).append(parse_single_instance_stats(instance_dir))
    return stats

def cpu_state_time_perc(data, cpu_id, exp_time):
    cpu_str = "CPU{}".format(cpu_id)
    state_names = ['POLL', 'C1', 'C1E', 'C6']
    state_time_perc = []
    total_state_time = 0
    time_us = 0
    # determine time window of measurements
    for state_name in state_names:
        if state_name in data[cpu_str]:
            (ts_start, val_start) = data[cpu_str][state_name]['time'][0]
            (ts_end, val_end) = data[cpu_str][state_name]['time'][-1]
            time_us = max(time_us, (ts_end - ts_start) * 1000000.0)
            total_state_time += val_end - val_start    
    time_us = max(time_us, total_state_time)
    # FIXME: time duration is currently hardcoded at 120s (120000000us)
    extra_c6_time_us = time_us - 120000000 #(exp_time*1000000) #
    # calculate percentage
    for state_name in state_names:
        if state_name == 'C6':
            extra = extra_c6_time_us
        else:
            extra = 0
        if state_name in data[cpu_str]:
            (ts_start, val_start) = data[cpu_str][state_name]['time'][0]
            (ts_end, val_end) = data[cpu_str][state_name]['time'][-1]
            state_time_perc.append((val_end-val_start-extra)/time_us)
    # calculate C0 as the remaining time 
    state_time_perc[0] = 1 - sum(state_time_perc[1:5])
    state_names[0] = 'C0' 
    return state_time_perc
    
    
def cpu_state_time(data, cpu_id):
    cpu_str = "CPU{}".format(cpu_id)
    #state_names = ['POLL', 'C1', 'C1E', 'C6']
    state_names = ['C6', 'C1E', 'C1', 'POLL']
    state_time = []
    total_state_time = 0
    time_us = 0
    # determine time window of measurements
    for state_name in state_names:
        if state_name in data[cpu_str]:
            (ts_start, val_start) = data[cpu_str][state_name]['time'][0]
            (ts_end, val_end) = data[cpu_str][state_name]['time'][-1]
            time_us = max(time_us, (ts_end - ts_start) * 1000000.0)
            total_state_time += val_end - val_start 
    
    # FIXME: time duration is currently hardcoded at 120s (120000000us)
    extra_c6_time_us = total_state_time - 120000000 #(exp_time*1000000) #
    # calculate percentage
    
    for state_name in state_names:
        (ts_start, val_start) = data[cpu_str][state_name]['time'][0]
        (ts_end, val_end) = data[cpu_str][state_name]['time'][-1]
        total_state_time = val_end - val_start
        
        if state_name == 'C6' and extra_c6_time_us < total_state_time:
            extra = extra_c6_time_us
            extra_c6_time_us=0
        elif state_name == 'C6' and extra_c6_time_us > total_state_time:
            extra = total_state_time
            extra_c6_time_us = extra_c6_time_us - total_state_time
        elif state_name == 'C1E' and extra_c6_time_us < total_state_time:
            extra = extra_c6_time_us
            extra_c6_time_us=0
        elif state_name == 'C1E' and extra_c6_time_us > total_state_time:            
           extra = total_state_time
           extra_c6_time_us = extra_c6_time_us - total_state_time
        elif state_name == 'C1' and extra_c6_time_us < total_state_time:
            extra = extra_c6_time_us
            extra_c6_time_us=0
        elif state_name == 'C1' and extra_c6_time_us > total_state_time:            
           extra = total_state_time
           extra_c6_time_us = extra_c6_time_us - total_state_time  
        else:
            extra = 0
            
        
        if state_name in data[cpu_str]:
            
            (ts_start, val_start) = data[cpu_str][state_name]['time'][0]
            (ts_end, val_end) = data[cpu_str][state_name]['time'][-1]
            state_time.append((val_end-val_start-extra))
        
    # calculate C0 as the remaining time 
    state_time_c0 = 120000000 - sum(state_time[0:3]) 
    state_time.reverse()
    return state_time

def avg_state_time_perc(stats, cpu_id_list,  exp_time):
    for stat in stats:
        total_state_time_perc = [0]*4
        cpu_count = 0
        for cpud_id in cpu_id_list:
            cpu_count += 1
            total_state_time_perc = [a + b for a, b in zip(total_state_time_perc, cpu_state_time_perc(stats, cpud_id, exp_time))]
        avg_state_time_perc = [a/b for a, b in zip(total_state_time_perc, [cpu_count]*len(total_state_time_perc))]
    return avg_state_time_perc
    
    
def sum_state_time_perc(stats, cpu_id_list):
    for stat in stats:
        total_state_time = [0]*4
        cpu_count = 0
        for cpud_id in cpu_id_list:
            cpu_count += 1
            total_state_time = [a + b for a, b in zip(total_state_time, cpu_state_time(stats, cpud_id))]      
    
        #avg_state_time_perc = [a/b for a, b in zip(total_state_time, [cpu_count]*len(total_state_time))]
    return total_state_time
    

def get_residency_per_target_qps(stats, system_conf, qps_list):
    # determine used C-states
    state_names = ['C0']
    check_state_names = ['C1', 'C1E', 'C6']
    for state_name in check_state_names:
        instance_name = system_conf_fullname(system_conf) + shortname('1500')      
        if state_name in stats[instance_name][0]['server']['CPU0']:
            state_names.append(state_name)
    raw = [[]] * (1+len(state_names))
    raw[0] = (['State'] + [str(q) for q in qps_list])
    for state_id in range(0, len(state_names)):
        raw[1+state_id] = [state_names[state_id]]
    for qps in qps_list:
        instance_name = system_conf_fullname(system_conf) + shortname(qps)
        time_perc_list = []
        #hardcoded to 400 s for minimum experiment
        exp_time=int(400*min(qps_list)/qps)
        for stat in stats[instance_name]:
            
            time_perc_list.append(avg_state_time_perc(stat['server'], range(0, 10), exp_time))
       
        avg_time_perc = [0]*len(state_names)
        for time_perc in time_perc_list:
            avg_time_perc = [a+b for a, b in zip(avg_time_perc, time_perc)]
        avg_time_perc = [a/len(time_perc_list) for a in avg_time_perc]
        
        for state_id in range(0, len(state_names)):
            row = raw[1 + state_id]
            row.append(avg_time_perc[state_id])
    return raw
    
def get_residency_per_target_qps_seconds(stats, system_conf, qps_list):
    # determine used C-states
    state_names = ['C0']
    check_state_names = ['C1', 'C1E', 'C6']
    for state_name in check_state_names:
        instance_name = system_conf_fullname(system_conf) + shortname('1500')
        if state_name in stats[instance_name][0]['server']['CPU0']:
            state_names.append(state_name)
   
    
    raw = [[]] * (1+len(state_names))
    raw[0] = (['State'] + [str(q) for q in qps_list])
    for state_id in range(0, len(state_names)):
        raw[1+state_id] = [state_names[state_id]]
    for qps in qps_list:
        instance_name = system_conf_fullname(system_conf) + shortname(qps)
         
        time_list=[]
        for stat in stats[instance_name]:
            
            time_list.append(sum_state_time_perc(stat['server'], range(0, 10)))
        
       
        avg_time_perc = [0]*len(state_names)
        for time_perc in time_list:
            avg_time_perc = [a+b for a, b in zip(avg_time_perc, time_perc)]
        #avg_time_percavg_time_perc = [a/len(time_list) for a in avg_time_perc]
       
        for state_id in range(0, len(state_names)):
            row = raw[1 + state_id]
            row.append(avg_time_perc[state_id])
        
    return raw

def cpu_state_usage(data, cpu_id):
    cpu_str = "CPU{}".format(cpu_id)
    state_names = ['POLL', 'C1', 'C1E', 'C6']
    state_time_perc = []
    total_state_time = 0
    time_us = 0
    state_usage_vec = []
    for state_name in state_names:
        if state_name in data[cpu_str]:
            (ts_start, val_start) = data[cpu_str][state_name]['usage'][0]
            (ts_end, val_end) = data[cpu_str][state_name]['usage'][-1]
            state_usage = val_end - val_start
            state_usage_vec.append(state_usage)
    return state_usage_vec

def avg_state_usage(stats, cpu_id_list):
    total_state_usage = [0]*4
    cpu_count = 0
    for cpud_id in cpu_id_list:
        cpu_count += 1
        total_state_usage = [a + b for a, b in zip(total_state_usage, cpu_state_usage(stats, cpud_id))]
    avg_state_usage = [a/b for a, b in zip(total_state_usage, [cpu_count]*len(total_state_usage))]
    return avg_state_usage

def get_usage_per_target_qps(stats, system_conf, qps_list):
    # determine used C-states
    state_names = ['POLL']
    check_state_names = ['C1', 'C1E', 'C6']
    for state_name in check_state_names:
        instance_name = system_conf_fullname(system_conf) + shortname('1500')
        if state_name in stats[instance_name][0]['server']['CPU0']:
            state_names.append(state_name)
    raw = [[]] * (1+len(state_names))
    raw[0] = (['State'] + [str(q) for q in qps_list])
    for state_id in range(0, len(state_names)):
        raw[1+state_id] = [state_names[state_id]]
    for qps in qps_list:
        instance_name = system_conf_fullname(system_conf) + shortname(qps)
        usage_list = []
        for stat in stats[instance_name]:
            usage_list.append(avg_state_usage(stat['server'], range(0, 10)))
        avg_usage = [0]*len(state_names)
        for usage in usage_list:
            avg_usage = [a+b for a, b in zip(avg_usage, usage)]
        avg_usage = [a/len(usage_list) for a in avg_usage]
        for state_id in range(0, len(state_names)):
            row = raw[1 + state_id]
            row.append(avg_usage[state_id])
    return raw

def plot_residency_per_target_qps(stats, system_conf, qps_list):
    raw = get_residency_per_target_qps(stats, system_conf, qps_list)
    width = 0.35        
    fig, ax = plt.subplots()
    header_row = raw[0]
    bottom = [0] * len(header_row[1:])
    labels = [str(int(int(c)/1000))+'K' for c in header_row[1:]]
    for row in raw[1:]:
        state_name = row[0]
        vals = [float(c) for c in row[1:]]
        ax.bar(labels, vals, width, label=state_name, bottom=bottom)
        for i, val in enumerate(vals):
            bottom[i] += val    
    ax.set_ylabel('C-State Residency (fraction)')
    ax.set_xlabel('Request Rate (QPS)')
    ax.legend()
    plt.title(system_conf_fullname(system_conf))
    return fig

def get_latency_per_target_qps(stats, system_confs, qps_list):
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    raw = []
    header_row = []
    header_row.append('QPS')
    for system_conf in system_confs:
        header_row.append(system_conf_shortname(system_conf) + 'read_avg_avg') 
        header_row.append(system_conf_shortname(system_conf) + 'read_avg_std') 
        header_row.append(system_conf_shortname(system_conf) + 'read_p99_avg') 
        header_row.append(system_conf_shortname(system_conf) + 'read_p99_std')
        header_row.append(system_conf_shortname(system_conf) + 'update_avg_avg') 
        header_row.append(system_conf_shortname(system_conf) + 'update_avg_std') 
        header_row.append(system_conf_shortname(system_conf) + 'update_p99_avg') 
        header_row.append(system_conf_shortname(system_conf) + 'update_p99_std')
    raw.append(header_row)
    for i, qps in enumerate(qps_list):
        row = [str(qps)]
        for system_conf in system_confs:
                        
            read_avg = []
            read_p99 = []
            update_avg = []
            update_p99 = []
            
            instance_name = system_conf_fullname(system_conf) + shortname(qps)
            for stat in stats[instance_name]:
                mcperf_stats = stat['mcperf']
                read_avg.append(mcperf_stats['read']['avg'])
                read_p99.append(mcperf_stats['read']['p99'])
                update_avg.append(mcperf_stats['update']['avg'])
                update_p99.append(mcperf_stats['update']['p99'])
                
            if len(read_avg) >= 5:
                read_avg.remove(min(read_avg))
                read_avg.remove(max(read_avg))
                read_p99.remove(min(read_p99))
                read_p99.remove(max(read_p99))
                
            if len(update_avg) >= 5:
                update_avg.remove(min(update_avg))
                update_avg.remove(max(update_avg))
                update_p99.remove(min(update_p99))
                update_p99.remove(max(update_p99))
                
            row.append(str(statistics.mean(read_avg)))
            row.append(str(statistics.stdev(read_avg)) if len(read_avg) > 1 else 'N/A')
            row.append(str(statistics.mean(read_p99)))
            row.append(str(statistics.stdev(read_p99)) if len(read_p99) > 1 else 'N/A')
            row.append(str(statistics.mean(update_avg)))
            row.append(str(statistics.stdev(update_avg)) if len(update_avg) > 1 else 'N/A')
            row.append(str(statistics.mean(update_p99)))
            row.append(str(statistics.stdev(update_p99)) if len(update_p99) > 1 else 'N/A')
        raw.append(row)
    return raw

def column_matches(filter, column_name):
    for f in filter:
        if f in column_name:
            return True
    return False

def plot_X_per_target_qps(raw, qps_list, xlabel, ylabel, filter=None):
    axis_scale = 0.001
    fig, ax = plt.subplots()
    axis_qps_list = [q *axis_scale for q in qps_list]
    header_row = raw[0]
    data_rows = raw[1:]
    for i, y_column_name in enumerate(header_row[1::2]):
        if filter and not column_matches(filter, y_column_name):
            continue
        y_vals = []
        y_vals_err = []
        y_column_id = 1 + i * 2
        for row_id, row in enumerate(data_rows):
            y_vals.append(float(data_rows[row_id][y_column_id]))
            y_val_err = data_rows[row_id][y_column_id+1] 
            y_vals_err.append(float(y_val_err) if y_val_err != 'N/A' else 0)
        plt.errorbar(axis_qps_list, y_vals, yerr = y_vals_err, label=y_column_name)

    ax.set_ylabel(ylabel)
    ax.set_xlabel(xlabel)
    ax.legend(loc='lower right')

    return fig

def plot_latency_per_target_qps(stats, system_confs, qps_list, filter=None):
    raw = get_latency_per_target_qps(stats, system_confs, qps_list)
    return plot_X_per_target_qps(raw, qps_list, 'Request Rate (KQPS)', 'Latency (us)', filter)

def get_total_qps_per_target_qps(stats, system_confs, qps_list):
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    raw = []
    header_row = []
    header_row.append('QPS')
    for system_conf in system_confs:
        header_row.append(system_conf_shortname(system_conf) + 'Total-QPS-avg') 
        header_row.append(system_conf_shortname(system_conf) + 'Total-QPS-std') 
    raw.append(header_row)
    for i, qps in enumerate(qps_list):
        row = [str(qps)]
        for system_conf in system_confs:
            total_qps = []
            instance_name = system_conf_fullname(system_conf) + shortname(qps)
            for stat in stats[instance_name]:
                mcperf_stats = stat['mcperf']
                total_qps.append(mcperf_stats['total_qps'])
            row.append(str(statistics.mean(total_qps)))
            row.append(str(statistics.stdev(total_qps)) if len(total_qps) > 1 else 'N/A')
        raw.append(row)
    return raw

def plot_total_qps_per_target_qps(stats, system_confs, qps_list, filter=None):
    raw = get_total_qps_per_target_qps(stats, system_confs, qps_list)
    return plot_X_per_target_qps(raw, qps_list, 'Request Rate (KQPS)', 'Total Rate (KQPS)', filter)

def avg_power(timeseries):
    total_val = 0
    for (ts, val) in timeseries:
        total_val += val
    time = timeseries[-1][0] - timeseries[0][0]
    return total_val / time

def sum_perf(timeseries):
    values_only=[]
    for (ts, val) in timeseries:
        values_only.append(val)
    
    return values_only

def avg_util(timeseries):
    total_val = 0
    for (ts, val) in timeseries:
        total_val += val
    time = timeseries[-1][0] - timeseries[0][0]
    return total_val / time
    
def avg_pcie(timeseries):
    total_val = []
    
    for (ts, val) in timeseries:
        #5 fixed due to the number of seconds sampling spend on each timer with pcm
        total_val.append(val/5)
        
    return sum(total_val)/len(total_val)

def get_power_per_target_qps(stats, system_confs, qps_list):
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    raw = []
    header_row = []
    header_row.append('QPS')
    for system_conf in system_confs:
        header_row.append(system_conf_shortname(system_conf) + 'power-pkg-avg') 
        header_row.append(system_conf_shortname(system_conf) + 'power-pkg-std') 
        header_row.append(system_conf_shortname(system_conf) + 'power-ram-avg') 
        header_row.append(system_conf_shortname(system_conf) + 'power-ram-std') 
    raw.append(header_row)
    for i, qps in enumerate(qps_list):
        row = [str(qps)]
        for system_conf in system_confs:
            power_pkg = []
            power_ram = []
            instance_name = system_conf_fullname(system_conf) + shortname(qps)
            for stat in stats[instance_name]:
                system_stats = stat['server']
                power_pkg.append(avg_power(system_stats['power/energy-pkg/']))
                power_ram.append(avg_power(system_stats['power/energy-ram/']))
            row.append(str(statistics.mean(power_pkg)))
            row.append(str(statistics.stdev(power_pkg)) if len(power_pkg) > 1 else 'N/A' )
            row.append(str(statistics.mean(power_ram)))
            row.append(str(statistics.stdev(power_ram)) if len(power_ram) > 1 else 'N/A')
        raw.append(row)
    return raw

def get_util_per_target_qps(stats, system_confs, qps_list):
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    raw = []
    header_row = []
    header_row.append('QPS')
    for system_conf in system_confs:
        header_row.append(system_conf_shortname(system_conf) + 'cpu-util-avg') 
        header_row.append(system_conf_shortname(system_conf) + 'cpu-util-std') 
    raw.append(header_row)
    for i, qps in enumerate(qps_list):
        row = [str(qps)]
        for system_conf in system_confs:
            cpu_util = []
            instance_name = system_conf_fullname(system_conf) + shortname(qps)
            for stat in stats[instance_name]:
                system_stats = stat['server']
                cpu_util.append(avg_util(system_stats['cpu_util']))
            row.append(str(statistics.mean(cpu_util)*2))
            row.append(str(statistics.stdev(cpu_util)) if len(cpu_util) > 1 else 'N/A' )
        raw.append(row)
    return raw

def get_rapl_power_per_target_qps(stats, system_confs, qps_list):
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    raw = []
    header_row = []
    header_row.append('QPS')
    for system_conf in system_confs:
        header_row.append(system_conf_shortname(system_conf) + 'power-pkg-0-avg') 
        header_row.append(system_conf_shortname(system_conf) + 'power-pkg-0-std') 
        header_row.append(system_conf_shortname(system_conf) + 'power-pkg-1-avg') 
        header_row.append(system_conf_shortname(system_conf) + 'power-pkg-1-std') 
        header_row.append(system_conf_shortname(system_conf) + 'power-dram-avg') 
        header_row.append(system_conf_shortname(system_conf) + 'power-dram-std')
    raw.append(header_row)
    for i, qps in enumerate(qps_list):
        row = [str(qps)]
        for system_conf in system_confs:
            power_pkg_0 = []
            power_pkg_1 = []
            power_dram = []
            
            instance_name = system_conf_fullname(system_conf) + shortname(qps)
            for stat in stats[instance_name]:
                system_stats = stat['server']
                power_pkg_0.append((system_stats['package-0'][0]))
                power_pkg_1.append((system_stats['package-1'][0]))
                power_dram.append((system_stats['dram'][0]))
                            
            row.append(str(statistics.mean(power_pkg_0)))
            row.append(str(statistics.stdev(power_pkg_0)) if len(power_pkg_0) > 1 else 'N/A' )
            row.append(str(statistics.mean(power_pkg_1)))
            row.append(str(statistics.stdev(power_pkg_1)) if len(power_pkg_1) > 1 else 'N/A' )
            row.append(str(statistics.mean(power_dram)))
            row.append(str(statistics.stdev(power_dram)) if len(power_dram) > 1 else 'N/A')
        raw.append(row)
    return raw

def get_perf_count_per_target_qps(stats, system_confs, qps_list):
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    raw = []
    header_row = []
    header_row.append('QPS')
    for system_conf in system_confs:
        
        header_row.append(system_conf_shortname(system_conf) + 'inst_retired.any-avg')
        header_row.append(system_conf_shortname(system_conf) + 'br_inst_retired.all_branches-avg')
        header_row.append(system_conf_shortname(system_conf) + 'br_misp_retired.all_branches-avg')
        header_row.append(system_conf_shortname(system_conf) + 'dtlb_load_misses.miss_causes_a_walk-avg')
        header_row.append(system_conf_shortname(system_conf) + 'dtlb_load_misses.stlb_hit-avg')
        #header_row.append(system_conf_shortname(system_conf) + 'dtlb_load_misses.walk_active-avg')
        header_row.append(system_conf_shortname(system_conf) + 'itlb_misses.miss_causes_a_walk-avg')
        header_row.append(system_conf_shortname(system_conf) + 'itlb_misses.stlb_hit-avg')
        header_row.append(system_conf_shortname(system_conf) + 'dtlb_store_misses.miss_causes_a_walk-avg')
        header_row.append(system_conf_shortname(system_conf) + 'dtlb_store_misses.stlb_hit-avg')
        #header_row.append(system_conf_shortname(system_conf) + 'l1d_pend_miss.pending_cycles-avg')
        header_row.append(system_conf_shortname(system_conf) + 'L1-dcache-load-misses-avg')
        header_row.append(system_conf_shortname(system_conf) + 'L1-dcache-loads-avg')
        header_row.append(system_conf_shortname(system_conf) + 'L1-icache-load-misses-avg') 
        header_row.append(system_conf_shortname(system_conf) + 'mem_inst_retired.all_loads-avg')
        header_row.append(system_conf_shortname(system_conf) + 'mem_inst_retired.all_stores-avg')
        header_row.append(system_conf_shortname(system_conf) + 'mem_load_retired.l2_miss-avg')
        header_row.append(system_conf_shortname(system_conf) + 'mem_load_retired.l2_hit-avg')
        header_row.append(system_conf_shortname(system_conf) + 'mem_load_retired.l3_miss-avg')
        header_row.append(system_conf_shortname(system_conf) + 'mem_load_retired.l3_hit-avg')
        header_row.append(system_conf_shortname(system_conf) + 'instructions-avg')
        header_row.append(system_conf_shortname(system_conf) + 'cycles-avg') 
        #header_row.append(system_conf_shortname(system_conf) + 'cache-misses-avg')
        header_row.append(system_conf_shortname(system_conf) + 'branch-misses-avg')        
        header_row.append(system_conf_shortname(system_conf) + 'Frequency-avg')
        header_row.append(system_conf_shortname(system_conf) + 'IPC-avg')
        header_row.append(system_conf_shortname(system_conf) + 'Perf-Time-avg')
        
       
        header_row.append(system_conf_shortname(system_conf) + 'inst_retired.any-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'br_inst_retired.all_branches-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'br_misp_retired.all_branches-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'dtlb_load_misses.miss_causes_a_walk-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'dtlb_load_misses.stlb_hit-stdv')
        #header_row.append(system_conf_shortname(system_conf) + 'dtlb_load_misses.walk_active-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'itlb_misses.miss_causes_a_walk-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'itlb_misses.stlb_hit-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'dtlb_store_misses.miss_causes_a_walk-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'dtlb_store_misses.stlb_hit-stdv')
        #header_row.append(system_conf_shortname(system_conf) + 'l1d_pend_miss.pending_cycles-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'L1-dcache-load-misses-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'L1-dcache-loads-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'L1-icache-load-misses-stdv')
        
        header_row.append(system_conf_shortname(system_conf) + 'mem_inst_retired.all_loads-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'mem_inst_retired.all_stores-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'mem_load_retired.l2_miss-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'mem_load_retired.l2_hit-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'mem_load_retired.l3_miss-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'mem_load_retired.l3_hit-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'instructions-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'cycles-stdv')
        #header_row.append(system_conf_shortname(system_conf) + 'cache-misses-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'branch-misses-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'Frequency-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'IPC-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'Perf-Time-stdv')
        
    raw.append(header_row)
    for i, qps in enumerate(qps_list):
        row = [str(qps)]
        for system_conf in system_confs:
            inst_retired_any = []
            br_inst_retired_all_branches = []
            br_misp_retired_all_branches = []
            dtlb_load_misses_miss_causes_a_walk = []
            dtlb_load_misses_stlb_hit = []
            #dtlb_load_misses_walk_active = []
            itlb_misses_miss_causes_a_walk = []
            itlb_misses_stlb_hit = []
            dtlb_store_misses_miss_causes_a_walk = []
            dtlb_store_misses_stlb_hit = []
             
            #l1d_pend_miss_pending_cycles = []
            L1_dcache_load_misses = []
            L1_dcache_loads = []
            L1_icache_load_misses = []
            
            mem_inst_retired_all_loads = []
            mem_inst_retired_all_stores = []
            mem_load_retired_l2_miss = []
            mem_load_retired_l2_hit = []
            mem_load_retired_l3_miss = []
            mem_load_retired_l3_hit = []
            instructions = []
            cycles = []
            #cache_misses = []
            branch_misses = []
            Frequency = []
            IPC = []
            Perf_Time = []
            
            instance_name = system_conf_fullname(system_conf) + shortname(qps)
            for stat in stats[instance_name]:
                system_stats = stat['server']
                
                inst_retired_any.append(sum(sum_perf(system_stats['inst_retired_any'])))
                br_inst_retired_all_branches.append(sum(sum_perf(system_stats['br_inst_retired_all_branches'])))
                br_misp_retired_all_branches.append(sum(sum_perf(system_stats['br_misp_retired_all_branches'])))
                dtlb_load_misses_miss_causes_a_walk.append(sum(sum_perf(system_stats['dtlb_load_misses_miss_causes_a_walk'])))          
                dtlb_load_misses_stlb_hit.append(sum(sum_perf(system_stats['dtlb_load_misses_stlb_hit'])))                
                #dtlb_load_misses_walk_active.append(sum(sum_perf(system_stats['dtlb_load_misses_walk_active'])))                
                itlb_misses_miss_causes_a_walk.append(sum(sum_perf(system_stats['itlb_misses_miss_causes_a_walk'])))                
                itlb_misses_stlb_hit.append(sum(sum_perf(system_stats['itlb_misses_stlb_hit'])))
                dtlb_store_misses_miss_causes_a_walk.append(sum(sum_perf(system_stats['dtlb_store_misses_miss_causes_a_walk'])))
                dtlb_store_misses_stlb_hit.append(sum(sum_perf(system_stats['dtlb_store_misses_stlb_hit'])))
                L1_dcache_load_misses.append(sum(sum_perf(system_stats['L1-dcache-load-misses'])))
                L1_dcache_loads.append(sum(sum_perf(system_stats['L1-dcache-loads'])))
                L1_icache_load_misses.append(sum(sum_perf(system_stats['L1-icache-load-misses'])))
                
                
                #l1d_pend_miss_pending_cycles.append(sum(sum_perf(system_stats['l1d_pend_miss_pending_cycles'])))                
                mem_inst_retired_all_loads.append(sum(sum_perf(system_stats['mem_inst_retired_all_loads'])))                
                mem_inst_retired_all_stores.append(sum(sum_perf(system_stats['mem_inst_retired_all_stores'])))                
                mem_load_retired_l2_miss.append(sum(sum_perf(system_stats['mem_load_retired_l2_miss'])))                
                mem_load_retired_l2_hit.append(sum(sum_perf(system_stats['mem_load_retired_l2_hit'])))                
                mem_load_retired_l3_miss.append(sum(sum_perf(system_stats['mem_load_retired_l3_miss'])))                
                mem_load_retired_l3_hit.append(sum(sum_perf(system_stats['mem_load_retired_l3_hit']))) 
                
                instructions.append(sum(sum_perf(system_stats['instructions'])))
                cycles.append(sum(sum_perf(system_stats['cycles'])))
                #cache_misses.append(sum(sum_perf(system_stats['cache-misses'])))
                branch_misses.append(sum(sum_perf(system_stats['branch-misses'])))
                
                
                Frequency.append((sum(sum_perf(system_stats['GHz'])))/5)
                IPC.append(sum(sum_perf(system_stats['insn_per_cycle']))/5)
                Perf_Time.append(sum(sum_perf(system_stats['seconds_time_elapsed'])))
            
    
                inst_retired_any = [i for i in inst_retired_any if i != 0]
                br_inst_retired_all_branches = [i for i in br_inst_retired_all_branches if i != 0]
                br_misp_retired_all_branches = [i for i in br_misp_retired_all_branches if i != 0]
                dtlb_load_misses_miss_causes_a_walk = [i for i in dtlb_load_misses_miss_causes_a_walk if i != 0]
                dtlb_load_misses_stlb_hit = [i for i in dtlb_load_misses_stlb_hit if i != 0]
                #dtlb_load_misses_walk_active = [i for i in dtlb_load_misses_walk_active if i != 0]
                itlb_misses_miss_causes_a_walk = [i for i in itlb_misses_miss_causes_a_walk if i != 0]
                itlb_misses_stlb_hit = [i for i in itlb_misses_stlb_hit if i != 0]
                dtlb_store_misses_miss_causes_a_walk = [i for i in dtlb_store_misses_miss_causes_a_walk if i != 0]
                dtlb_store_misses_stlb_hit = [i for i in dtlb_store_misses_stlb_hit if i != 0]
                L1_dcache_load_misses = [i for i in L1_dcache_load_misses if i != 0]
                L1_dcache_loads = [i for i in L1_dcache_loads if i != 0]
                L1_icache_load_misses = [i for i in L1_icache_load_misses if i != 0]
                #l1d_pend_miss_pending_cycles = [i for i in l1d_pend_miss_pending_cycles if i != 0]
                mem_inst_retired_all_loads = [i for i in mem_inst_retired_all_loads if i != 0]
                mem_inst_retired_all_stores = [i for i in mem_inst_retired_all_stores if i != 0]
                mem_load_retired_l2_miss = [i for i in mem_load_retired_l2_miss if i != 0]
                mem_load_retired_l2_hit = [i for i in mem_load_retired_l2_hit if i != 0]
                mem_load_retired_l3_miss = [i for i in mem_load_retired_l3_miss if i != 0]
                mem_load_retired_l3_hit = [i for i in mem_load_retired_l3_hit if i != 0]
                instructions = [i for i in instructions if i != 0]
                cycles = [i for i in cycles if i != 0]
                #cache_misses = [i for i in cache_misses if i != 0]
                branch_misses = [i for i in branch_misses if i != 0]
                Frequency = [i for i in Frequency if i != 0]
                IPC = [i for i in IPC if i != 0]
                Perf_Time = [i for i in Perf_Time if i != 0]
                             
            row.append(str(statistics.mean(inst_retired_any)))
            row.append(str(statistics.mean(br_inst_retired_all_branches)))
            row.append(str(statistics.mean(br_misp_retired_all_branches)))
            row.append(str(statistics.mean(dtlb_load_misses_miss_causes_a_walk)))
            row.append(str(statistics.mean(dtlb_load_misses_stlb_hit)))
            #row.append(str(statistics.mean(dtlb_load_misses_walk_active)))
            row.append(str(statistics.mean(itlb_misses_miss_causes_a_walk)))
            row.append(str(statistics.mean(itlb_misses_stlb_hit)))
            row.append(str(statistics.mean(dtlb_store_misses_miss_causes_a_walk)))
            row.append(str(statistics.mean(dtlb_store_misses_stlb_hit)))
            row.append(str(statistics.mean(L1_dcache_load_misses)))
            row.append(str(statistics.mean(L1_dcache_loads)))
            row.append(str(statistics.mean(L1_icache_load_misses)))
            
            
            #row.append(str(statistics.mean(l1d_pend_miss_pending_cycles)))
            row.append(str(statistics.mean(mem_inst_retired_all_loads)))
            row.append(str(statistics.mean(mem_inst_retired_all_stores)))
            row.append(str(statistics.mean(mem_load_retired_l2_miss)))
            row.append(str(statistics.mean(mem_load_retired_l2_hit)))
            row.append(str(statistics.mean(mem_load_retired_l3_miss)))
            row.append(str(statistics.mean(mem_load_retired_l3_hit)))
            row.append(str(statistics.mean(instructions)))
            #row.append(str(statistics.mean(cache_misses)))
            row.append(0)#row.append(str(statistics.mean(cycles)))
            row.append(0)#row.append(str(statistics.mean(branch_misses)))
            row.append(0)#row.append(str(statistics.mean(Frequency)))
            row.append(0)#row.append(str(statistics.mean(IPC)))
            row.append(str(statistics.mean(Perf_Time)))
            
            row.append(str(statistics.stdev(inst_retired_any)) if len(inst_retired_any) > 1 else 'N/A' )
            row.append(str(statistics.stdev(br_inst_retired_all_branches)) if len(br_inst_retired_all_branches) > 1 else 'N/A')
            row.append(str(statistics.stdev(br_misp_retired_all_branches)) if len(br_misp_retired_all_branches) > 1 else 'N/A')
            row.append(str(statistics.stdev(dtlb_load_misses_miss_causes_a_walk)) if len(dtlb_load_misses_miss_causes_a_walk) > 1 else 'N/A')
            row.append(str(statistics.stdev(dtlb_load_misses_stlb_hit)) if len(dtlb_load_misses_stlb_hit) > 1 else 'N/A')
            #row.append(str(statistics.stdev(dtlb_load_misses_walk_active)) if len(dtlb_load_misses_walk_active) > 1 else 'N/A')
            row.append(str(statistics.stdev(itlb_misses_miss_causes_a_walk)) if len(itlb_misses_miss_causes_a_walk) > 1 else 'N/A')
            row.append(str(statistics.stdev(itlb_misses_stlb_hit)) if len(itlb_misses_stlb_hit) > 1 else 'N/A')
            row.append(str(statistics.stdev(dtlb_store_misses_miss_causes_a_walk)) if len(dtlb_load_misses_miss_causes_a_walk) > 1 else 'N/A')
            row.append(str(statistics.stdev(dtlb_store_misses_stlb_hit)) if len(dtlb_load_misses_stlb_hit) > 1 else 'N/A')
            #row.append(str(statistics.stdev(l1d_pend_miss_pending_cycles)) if len(l1d_pend_miss_pending_cycles) > 1 else 'N/A')
            row.append(str(statistics.stdev(L1_dcache_load_misses)) if len(L1_dcache_load_misses) > 1 else 'N/A')
            row.append(str(statistics.stdev(L1_dcache_loads)) if len(L1_dcache_loads) > 1 else 'N/A')
            row.append(str(statistics.stdev(L1_icache_load_misses)) if len(L1_icache_load_misses) > 1 else 'N/A')
            
            
            row.append(str(statistics.stdev(mem_inst_retired_all_loads)) if len(mem_inst_retired_all_loads) > 1 else 'N/A')
            row.append(str(statistics.stdev(mem_inst_retired_all_stores)) if len(mem_inst_retired_all_stores) > 1 else 'N/A')
            row.append(str(statistics.stdev(mem_load_retired_l2_miss)) if len(mem_load_retired_l2_miss) > 1 else 'N/A')
            row.append(str(statistics.stdev(mem_load_retired_l2_hit)) if len(mem_load_retired_l2_hit) > 1 else 'N/A')
            row.append(str(statistics.stdev(mem_load_retired_l3_miss)) if len(mem_load_retired_l3_miss) > 1 else 'N/A')
            row.append(str(statistics.stdev(mem_load_retired_l3_hit)) if len(mem_load_retired_l3_hit) > 1 else 'N/A')
            
            row.append(str(statistics.stdev(instructions)) if len(instructions) > 1 else 'N/A')
            #row.append(str(statistics.stdev(cache_misses)) if len(cache_misses) > 1 else 'N/A')
            row.append(str(statistics.stdev(cycles)) if len(cycles) > 1 else 'N/A')
            row.append(str(statistics.stdev(branch_misses)) if len(branch_misses) > 1 else 'N/A')
            row.append(str(statistics.stdev(Frequency)) if len(Frequency) > 1 else 'N/A')
            row.append(str(statistics.stdev(IPC)) if len(IPC) > 1 else 'N/A')
            row.append(str(statistics.stdev(Perf_Time)) if len(Perf_Time) > 1 else 'N/A' )
            
                        
        raw.append(row)
    return raw



def get_CPI_stack_qps(stats,system_confs, qps_list):
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    raw = []
    header_row = []
    header_row.append('QPS')
    for system_conf in system_confs:
        
        #Level 1 measurements events
        header_row.append('Frontend_Bound')
        header_row.append('Bad_Speculation')
        header_row.append('Backend_Bound')
        header_row.append('Retiring')
        
        #Level 2 measurements events
        header_row.append('Frontend_Bound.Fetch_Bandwidth')
        header_row.append('Frontend_Bound.Fetch_Latency')
        header_row.append('Bad_Speculation.Branch_Mispredicts')
        header_row.append('Bad_Speculation.Machine_Clears')
        header_row.append('Backend_Bound.Memory_Bound')
        header_row.append('Backend_Bound.Core_Bound')
        header_row.append('Retiring.Heavy_Operations')
        header_row.append('Retiring.Light_Operations')
        
        #Level 3 measurements events
        header_row.append('Frontend_Bound.Fetch_Bandwidth.MITE')
        header_row.append('Frontend_Bound.Fetch_Bandwidth.DSB')
        header_row.append('Frontend_Bound.Fetch_Latency.Branch_Resteers')
        header_row.append('Frontend_Bound.Fetch_Latency.DSB_Switches')
        header_row.append('Frontend_Bound.Fetch_Latency.ICache_Misses')
        header_row.append('Frontend_Bound.Fetch_Latency.ITLB_Misses')
        header_row.append('Frontend_Bound.Fetch_Latency.LCP') 
        header_row.append('Frontend_Bound.Fetch_Latency.MS_Switches')
        header_row.append('Backend_Bound.Memory_Bound.DRAM_Bound')
        header_row.append('Backend_Bound.Memory_Bound.L1_Bound')
        header_row.append('Backend_Bound.Memory_Bound.L2_Bound')
        header_row.append('Backend_Bound.Memory_Bound.L3_Bound')
        header_row.append('Backend_Bound.Memory_Bound.Store_Bound')
        header_row.append('Backend_Bound.Core_Bound.Divider')
        header_row.append('Backend_Bound.Core_Bound.Ports_Utilization')
        header_row.append('Retiring.Heavy_Operations.Few_Uops_Instructions')
        header_row.append('Retiring.Heavy_Operations.Microcode_Sequencer')
        header_row.append('Retiring.Light_Operations.FP_Arith')
        header_row.append('Retiring.Light_Operations.Fused_Instructions')
        header_row.append('Retiring.Light_Operations.Memory_Operations')
        header_row.append('Retiring.Light_Operations.Non_Fused_Branches')
        header_row.append('Retiring.Light_Operations.Nop_Instructions')

        #Level 4 measurements events
        header_row.append('Frontend_Bound_Fetch_Latency_Branch_Resteers_Unknown_Branches')
        header_row.append('Frontend_Bound_Fetch_Latency_Branch_Resteers_Mispredicts_Resteers')
        header_row.append('Frontend_Bound_Fetch_Latency_Branch_Resteers_Clears_Resteers')
        header_row.append('Frontend_Bound_Fetch_Bandwidth_MITE_Decoder0_Alone')
        header_row.append('Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load')
        header_row.append('Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store')
        header_row.append('Backend_Bound_Memory_Bound_L1_Bound_Store_Fwd_Blk')
        header_row.append('Backend_Bound_Memory_Bound_L1_Bound_Lock_Latency')
        header_row.append('Backend_Bound_Memory_Bound_L3_Bound_Contested_Accesses')
        header_row.append('Backend_Bound_Memory_Bound_L3_Bound_Data_Sharing')
        header_row.append('Backend_Bound_Memory_Bound_L3_Bound_SQ_Full')
        header_row.append('Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Bandwidth')
        header_row.append('Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency')
        header_row.append('Backend_Bound_Memory_Bound_Store_Bound_Store_Latency')
        header_row.append('Backend_Bound_Memory_Bound_Store_Bound_False_Sharing')
        header_row.append('Backend_Bound_Memory_Bound_L1_Bound_Split_Loads')
        header_row.append('Backend_Bound_Memory_Bound_L1_Bound_4K_Aliasing')
        header_row.append('Backend_Bound_Memory_Bound_L1_Bound_FB_Full')
        header_row.append('Backend_Bound_Memory_Bound_L3_Bound_L3_Hit_Latency')
        header_row.append('Backend_Bound_Memory_Bound_Store_Bound_Split_Stores')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_1')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_2')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m')
        header_row.append('Retiring_Light_Operations_FP_Arith_X87_Use')
        header_row.append('Retiring_Light_Operations_FP_Arith_FP_Scalar')
        header_row.append('Retiring_Light_Operations_FP_Arith_FP_Vector')
        header_row.append('Retiring_Heavy_Operations_Microcode_Sequencer_Assists')
        header_row.append('Retiring_Heavy_Operations_Microcode_Sequencer_CISC')

        #Level 5
        header_row.append('Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Hit')
        header_row.append('Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Miss')
        header_row.append('Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Hit')
        header_row.append('Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Miss')
        header_row.append('Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_Cache')
        header_row.append('Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Local_DRAM')
        header_row.append('Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_DRAM')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Serializing_Operation')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Mixing_Vectors')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization')
        header_row.append('Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_128b')
        header_row.append('Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_256b')
        header_row.append('Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_512b')


        #Level 6
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_0')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_1')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_5')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_6')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_2')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_3')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_4')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_7')

        # Metrics


        header_row.append('SLOTS')
        header_row.append('CoreIPC')
        header_row.append('Instructions')
        header_row.append('IpCall')
        header_row.append('IpTB')
        header_row.append('BpTkBranch')
        header_row.append('Cond_NT')
        header_row.append('Cond_TK')
        header_row.append('Mispredictions')
        header_row.append('IpMispredictions')
        header_row.append('Branch_Misprediction_Cost')
        header_row.append('CallRet')
        header_row.append('Jump')
        header_row.append('Memory_Bandwidth')
        header_row.append('Memory_Latency')
        header_row.append('Memory_Data_TLBs')
        header_row.append('CPI')
        header_row.append('Load_Miss_Real_Latency')
        header_row.append('MLP')
        header_row.append('L1MPKI')
        header_row.append('L1MPKI_Load')
        header_row.append('L2MPKI')
        header_row.append('L2MPKI_All')
        header_row.append('L2MPKI_Load')
        header_row.append('L2HPKI_All')
        header_row.append('L2HPKI_Load')
        header_row.append('L3MPKI')
        header_row.append('FB_HPKI')
        header_row.append('Page_Walks_Utilization')
        header_row.append('L1D_Cache_Fill_BW')
        header_row.append('L2_Cache_Fill_BW')
        header_row.append('L3_Cache_Fill_BW')
        header_row.append('L3_Cache_Access_BW')
        header_row.append('L2_Evictions_Silent_PKI')
        header_row.append('L2_Evictions_NonSilent_PKI')
        header_row.append('L1D_Cache_Fill_BW_1T')
        header_row.append('L2_Cache_Fill_BW_1T')
        header_row.append('L3_Cache_Fill_BW_1T')
        header_row.append('L3_Cache_Access_BW_1T')
        header_row.append('DRAM_BW_Use')
        header_row.append('MEM_Read_Latency')
        header_row.append('MEM_DRAM_Read_Latency')
        header_row.append('IO_Write_BW')
        header_row.append('IO_Read_BW')
        header_row.append('Branching_Overhead')
        header_row.append('IPC')
        header_row.append('UPI')
        header_row.append('FLOPc')
        header_row.append('Retire')
        header_row.append('Big_Code')
        header_row.append('Instruction_Fetch_BW')
        header_row.append('UpTB')
        header_row.append('IpBranch')
        header_row.append('Fetch_UpC')
        header_row.append('DSB_Coverage')
        header_row.append('DSB_Misses')
        header_row.append('IpDSB_Miss_Ret')
        header_row.append('CLKS')
        header_row.append('Execute_per_Issue')
        header_row.append('ILP')
        header_row.append('Execute')
        header_row.append('FP_Arith_Utilization')
        header_row.append('Core_Bound_Likely')
        header_row.append('GFLOPs')
        header_row.append('IpFLOP')
        header_row.append('IpArith') 
        header_row.append('IpArith_Scalar_SP')
        header_row.append('IpArith_Scalar_DP')
        header_row.append('IpArith_AVX128')
        header_row.append('IpArith_AVX256')
        header_row.append('IpArith_AVX512')
        header_row.append('CPU_Utilization')
        header_row.append('CORE_CLKS')
        header_row.append('SMT_2T_Utilization')
        header_row.append('IpLoad')
        header_row.append('IpStore')
        header_row.append('IpSWPF')
        header_row.append('DSB_Switch_Cost')
        header_row.append('Turbo_Utilization')
        header_row.append('Power_License0_Utilization')
        header_row.append('Power_License1_Utilization')
        header_row.append('Power_License2_Utilization')
        header_row.append('Kernel_Utilization')
        header_row.append('Kernel_CPI')
        header_row.append('IpFarBranch')
        header_row.append('Time')
        header_row.append('Socket_CLKS')


         #Level 1 measurements events
        header_row.append('Frontend_Bound-stdev')
        header_row.append('Bad_Speculation-stdev')
        header_row.append('Backend_Bound-stdev')
        header_row.append('Retiring-stdev')
        
        #Level 2 measurements events
        header_row.append('Frontend_Bound.Fetch_Bandwidth-stdev')
        header_row.append('Frontend_Bound.Fetch_Latency-stdev')
        header_row.append('Bad_Speculation.Branch_Mispredicts-stdev')
        header_row.append('Bad_Speculation.Machine_Clears-stdev')
        header_row.append('Backend_Bound.Memory_Bound-stdev')
        header_row.append('Backend_Bound.Core_Bound-stdev')
        header_row.append('Retiring.Heavy_Operations-stdev')
        header_row.append('Retiring.Light_Operations-stdev')
        
        #Level 3 measurements events
        header_row.append('Frontend_Bound.Fetch_Bandwidth.MITE-stdev')
        header_row.append('Frontend_Bound.Fetch_Bandwidth.DSB-stdev')
        header_row.append('Frontend_Bound.Fetch_Latency.Branch_Resteers-stdev')
        header_row.append('Frontend_Bound.Fetch_Latency.DSB_Switches-stdev')
        header_row.append('Frontend_Bound.Fetch_Latency.ICache_Misses-stdev')
        header_row.append('Frontend_Bound.Fetch_Latency.ITLB_Misses-stdev')
        header_row.append('Frontend_Bound.Fetch_Latency.LCP-stdev') 
        header_row.append('Frontend_Bound.Fetch_Latency.MS_Switches-stdev')
        header_row.append('Backend_Bound.Memory_Bound.DRAM_Bound-stdev')
        header_row.append('Backend_Bound.Memory_Bound.L1_Bound-stdev')
        header_row.append('Backend_Bound.Memory_Bound.L2_Bound-stdev')
        header_row.append('Backend_Bound.Memory_Bound.L3_Bound-stdev')
        header_row.append('Backend_Bound.Memory_Bound.Store_Bound-stdev')
        header_row.append('Backend_Bound.Core_Bound.Divider-stdev')
        header_row.append('Backend_Bound.Core_Bound.Ports_Utilization-stdev')
        header_row.append('Retiring.Heavy_Operations.Few_Uops_Instructions-stdev')
        header_row.append('Retiring.Heavy_Operations.Microcode_Sequencer-stdev')
        header_row.append('Retiring.Light_Operations.FP_Arith-stdev')
        header_row.append('Retiring.Light_Operations.Fused_Instructions-stdev')
        header_row.append('Retiring.Light_Operations.Memory_Operations-stdev')
        header_row.append('Retiring.Light_Operations.Non_Fused_Branches-stdev')
        header_row.append('Retiring.Light_Operations.Nop_Instructions-stdev')

        #Level 4 measurements events
        header_row.append('Frontend_Bound_Fetch_Latency_Branch_Resteers_Unknown_Branches-stdev')
        header_row.append('Frontend_Bound_Fetch_Latency_Branch_Resteers_Mispredicts_Resteers-stdev')
        header_row.append('Frontend_Bound_Fetch_Latency_Branch_Resteers_Clears_Resteers-stdev')
        header_row.append('Frontend_Bound_Fetch_Bandwidth_MITE_Decoder0_Alone-stdev')
        header_row.append('Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load-stdev')
        header_row.append('Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store-stdev')
        header_row.append('Backend_Bound_Memory_Bound_L1_Bound_Store_Fwd_Blk-stdev')
        header_row.append('Backend_Bound_Memory_Bound_L1_Bound_Lock_Latency-stdev')
        header_row.append('Backend_Bound_Memory_Bound_L3_Bound_Contested_Accesses-stdev')
        header_row.append('Backend_Bound_Memory_Bound_L3_Bound_Data_Sharing-stdev')
        header_row.append('Backend_Bound_Memory_Bound_L3_Bound_SQ_Full-stdev')
        header_row.append('Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Bandwidth-stdev')
        header_row.append('Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency-stdev')
        header_row.append('Backend_Bound_Memory_Bound_Store_Bound_Store_Latency-stdev')
        header_row.append('Backend_Bound_Memory_Bound_Store_Bound_False_Sharing-stdev')
        header_row.append('Backend_Bound_Memory_Bound_L1_Bound_Split_Loads-stdev')
        header_row.append('Backend_Bound_Memory_Bound_L1_Bound_4K_Aliasing-stdev')
        header_row.append('Backend_Bound_Memory_Bound_L1_Bound_FB_Full-stdev')
        header_row.append('Backend_Bound_Memory_Bound_L3_Bound_L3_Hit_Latency-stdev')
        header_row.append('Backend_Bound_Memory_Bound_Store_Bound_Split_Stores-stdev')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0-stdev')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_1-stdev')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_2-stdev')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m-stdev')
        header_row.append('Retiring_Light_Operations_FP_Arith_X87_Use-stdev')
        header_row.append('Retiring_Light_Operations_FP_Arith_FP_Scalar-stdev')
        header_row.append('Retiring_Light_Operations_FP_Arith_FP_Vector-stdev')
        header_row.append('Retiring_Heavy_Operations_Microcode_Sequencer_Assists-stdev')
        header_row.append('Retiring_Heavy_Operations_Microcode_Sequencer_CISC-stdev')

        #Level 5
        header_row.append('Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Hit-stdev')
        header_row.append('Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Miss-stdev')
        header_row.append('Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Hit-stdev')
        header_row.append('Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Miss-stdev')
        header_row.append('Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_Cache-stdev')
        header_row.append('Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Local_DRAM-stdev')
        header_row.append('Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_DRAM-stdev')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Serializing_Operation-stdev')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Mixing_Vectors-stdev')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization-stdev')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization-stdev')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization-stdev')
        header_row.append('Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_128b-stdev')
        header_row.append('Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_256b-stdev')
        header_row.append('Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_512b-stdev')


        #Level 6
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_0-stdev')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_1-stdev')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_5-stdev')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_6-stdev')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_2-stdev')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_3-stdev')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_4-stdev')
        header_row.append('Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_7-stdev')

        # Metrics


        header_row.append('SLOTS-stdev')
        header_row.append('CoreIPC-stdev')
        header_row.append('Instructions-stdev')
        header_row.append('IpCall-stdev')
        header_row.append('IpTB-stdev')
        header_row.append('BpTkBranch-stdev')
        header_row.append('Cond_NT-stdev')
        header_row.append('Cond_TK-stdev')
        header_row.append('Mispredictions-stdev')
        header_row.append('IpMispredictions-stdev')
        header_row.append('Branch_Misprediction_Cost-stdev')
        header_row.append('CallRet-stdev')
        header_row.append('Jump-stdev')
        header_row.append('Memory_Bandwidth-stdev')
        header_row.append('Memory_Latency-stdev')
        header_row.append('Memory_Data_TLBs-stdev')
        header_row.append('CPI-stdev')
        header_row.append('Load_Miss_Real_Latency-stdev')
        header_row.append('MLP-stdev')
        header_row.append('L1MPKI-stdev')
        header_row.append('L1MPKI_Load-stdev')
        header_row.append('L2MPKI-stdev')
        header_row.append('L2MPKI_All-stdev')
        header_row.append('L2MPKI_Load-stdev')
        header_row.append('L2HPKI_All-stdev')
        header_row.append('L2HPKI_Load-stdev')
        header_row.append('L3MPKI-stdev')
        header_row.append('FB_HPKI-stdev')
        header_row.append('Page_Walks_Utilization-stdev')
        header_row.append('L1D_Cache_Fill_BW-stdev')
        header_row.append('L2_Cache_Fill_BW-stdev')
        header_row.append('L3_Cache_Fill_BW-stdev')
        header_row.append('L3_Cache_Access_BW-stdev')
        header_row.append('L2_Evictions_Silent_PKI-stdev')
        header_row.append('L2_Evictions_NonSilent_PKI-stdev')
        header_row.append('L1D_Cache_Fill_BW_1T-stdev')
        header_row.append('L2_Cache_Fill_BW_1T-stdev')
        header_row.append('L3_Cache_Fill_BW_1T-stdev')
        header_row.append('L3_Cache_Access_BW_1T-stdev')
        header_row.append('DRAM_BW_Use-stdev')
        header_row.append('MEM_Read_Latency-stdev')
        header_row.append('MEM_DRAM_Read_Latency-stdev')
        header_row.append('IO_Write_BW-stdev')
        header_row.append('IO_Read_BW-stdev')
        header_row.append('Branching_Overhead-stdev')
        header_row.append('IPC-stdev')
        header_row.append('UPI-stdev')
        header_row.append('FLOPc-stdev')
        header_row.append('Retire-stdev')
        header_row.append('Big_Code-stdev')
        header_row.append('Instruction_Fetch_BW-stdev')
        header_row.append('UpTB-stdev')
        header_row.append('IpBranch-stdev')
        header_row.append('Fetch_UpC-stdev')
        header_row.append('DSB_Coverage-stdev')
        header_row.append('DSB_Misses-stdev')
        header_row.append('IpDSB_Miss_Ret-stdev')
        header_row.append('CLKS-stdev')
        header_row.append('Execute_per_Issue-stdev')
        header_row.append('ILP-stdev')
        header_row.append('Execute-stdev')
        header_row.append('FP_Arith_Utilization-stdev')
        header_row.append('Core_Bound_Likely-stdev')
        header_row.append('GFLOPs-stdev')
        header_row.append('IpFLOP-stdev')
        header_row.append('IpArith-stdev') 
        header_row.append('IpArith_Scalar_SP-stdev')
        header_row.append('IpArith_Scalar_DP-stdev')
        header_row.append('IpArith_AVX128-stdev')
        header_row.append('IpArith_AVX256-stdev')
        header_row.append('IpArith_AVX512-stdev')
        header_row.append('CPU_Utilization-stdev')
        header_row.append('CORE_CLKS-stdev')
        header_row.append('SMT_2T_Utilization-stdev')
        header_row.append('IpLoad-stdev')
        header_row.append('IpStore-stdev')
        header_row.append('IpSWPF-stdev')
        header_row.append('DSB_Switch_Cost-stdev')
        header_row.append('Turbo_Utilization-stdev')
        header_row.append('Power_License0_Utilization-stdev')
        header_row.append('Power_License1_Utilization-stdev')
        header_row.append('Power_License2_Utilization-stdev')
        header_row.append('Kernel_Utilization-stdev')
        header_row.append('Kernel_CPI-stdev')
        header_row.append('IpFarBranch-stdev')
        header_row.append('Time-stdev')
        header_row.append('Socket_CLKS-stdev')

        
    raw.append(header_row)
    for i, qps in enumerate(qps_list):
        row = [str(qps)]
        for system_conf in system_confs:
            
            Backend_Bound = []
            Backend_Bound_Core_Bound = []
            Backend_Bound_Core_Bound_Divider = []
            Backend_Bound_Core_Bound_Ports_Utilization = []
            Backend_Bound_Memory_Bound = []
            Backend_Bound_Memory_Bound_DRAM_Bound = []
            Backend_Bound_Memory_Bound_L1_Bound = []
            Backend_Bound_Memory_Bound_L2_Bound = []
            Backend_Bound_Memory_Bound_L3_Bound = []
            Backend_Bound_Memory_Bound_Store_Bound = []
            Bad_Speculation = []
            Bad_Speculation_Branch_Mispredicts = []
            Bad_Speculation_Machine_Clears = []
            Frontend_Bound = [] 
            Frontend_Bound_Fetch_Bandwidth = []
            Frontend_Bound_Fetch_Bandwidth_DSB = []
            Frontend_Bound_Fetch_Bandwidth_MITE = []
            Frontend_Bound_Fetch_Latency = []
            Frontend_Bound_Fetch_Latency_Branch_Resteers = []
            Frontend_Bound_Fetch_Latency_DSB_Switches = []
            Frontend_Bound_Fetch_Latency_ICache_Misses = []
            Frontend_Bound_Fetch_Latency_ITLB_Misses = []
            Frontend_Bound_Fetch_Latency_LCP = [] 
            Frontend_Bound_Fetch_Latency_MS_Switches = []
            Retiring = []        
            Retiring_Heavy_Operations = []
            Retiring_Heavy_Operations_Few_Uops_Instructions = []
            Retiring_Heavy_Operations_Microcode_Sequencer = []
            Retiring_Light_Operations = []
            Retiring_Light_Operations_FP_Arith = []
            Retiring_Light_Operations_Fused_Instructions = []
            Retiring_Light_Operations_Memory_Operations = []
            Retiring_Light_Operations_Non_Fused_Branches = []
            Retiring_Light_Operations_Nop_Instructions = []

            #Level 4
            Frontend_Bound_Fetch_Latency_Branch_Resteers_Unknown_Branches = []
            Frontend_Bound_Fetch_Latency_Branch_Resteers_Mispredicts_Resteers = []
            Frontend_Bound_Fetch_Latency_Branch_Resteers_Clears_Resteers = []
            Frontend_Bound_Fetch_Bandwidth_MITE_Decoder0_Alone = []
            Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load = []
            Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store = []
            Backend_Bound_Memory_Bound_L1_Bound_Store_Fwd_Blk = []
            Backend_Bound_Memory_Bound_L1_Bound_Lock_Latency = []
            Backend_Bound_Memory_Bound_L3_Bound_Contested_Accesses = []
            Backend_Bound_Memory_Bound_L3_Bound_Data_Sharing = []
            Backend_Bound_Memory_Bound_L3_Bound_SQ_Full = []
            Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Bandwidth = []
            Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency = []
            Backend_Bound_Memory_Bound_Store_Bound_Store_Latency = []
            Backend_Bound_Memory_Bound_Store_Bound_False_Sharing = []
            Backend_Bound_Memory_Bound_L1_Bound_Split_Loads = []
            Backend_Bound_Memory_Bound_L1_Bound_4K_Aliasing = []
            Backend_Bound_Memory_Bound_L1_Bound_FB_Full = []
            Backend_Bound_Memory_Bound_L3_Bound_L3_Hit_Latency = []
            Backend_Bound_Memory_Bound_Store_Bound_Split_Stores = []
            Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0 = []
            Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_1 = []
            Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_2 = []
            Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m = []
            Retiring_Light_Operations_FP_Arith_X87_Use = []
            Retiring_Light_Operations_FP_Arith_FP_Scalar = []
            Retiring_Light_Operations_FP_Arith_FP_Vector = []
            Retiring_Heavy_Operations_Microcode_Sequencer_Assists = []
            Retiring_Heavy_Operations_Microcode_Sequencer_CISC = []

            #Level 5
            Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Hit = []
            Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Miss = []
            Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Hit = []
            Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Miss = []
            Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_Cache = []
            Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Local_DRAM = []
            Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_DRAM = []
            Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Serializing_Operation = []
            Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Mixing_Vectors = []
            Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization = []
            Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization = []
            Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization = []
            Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_128b = []
            Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_256b = []
            Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_512b = []


            #Level 6
            Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_0 = []
            Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_1 = []
            Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_5 = []
            Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_6 = []
            Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_2 = []
            Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_3 = []
            Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_4 = []
            Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_7 = []


            #metrics

            SLOTS = []
            CoreIPC = []
            Instructions = []
            IpCall = []
            IpTB = []
            BpTkBranch = []
            Cond_NT = []
            Cond_TK = []
            Mispredictions = []
            IpMispredict = []
            Branch_Misprediction_Cost = []
            CallRet = []
            Jump = []
            Memory_Bandwidth = []
            Memory_Latency = []
            Memory_Data_TLBs = []
            CPI = []
            Load_Miss_Real_Latency = []
            MLP = []
            L1MPKI = []
            L1MPKI_Load = []
            L2MPKI = []
            L2MPKI_All = []
            L2MPKI_Load = []
            L2HPKI_All = []
            L2HPKI_Load = []
            L3MPKI = []
            FB_HPKI = []
            Page_Walks_Utilization = []
            L1D_Cache_Fill_BW = []
            L2_Cache_Fill_BW = []
            L3_Cache_Fill_BW = []
            L3_Cache_Access_BW = []
            L2_Evictions_Silent_PKI = []
            L2_Evictions_NonSilent_PKI = []
            L1D_Cache_Fill_BW_1T = []
            L2_Cache_Fill_BW_1T = []
            L3_Cache_Fill_BW_1T = []
            L3_Cache_Access_BW_1T = []
            DRAM_BW_Use = []
            MEM_Read_Latency = []
            MEM_DRAM_Read_Latency = []
            IO_Write_BW = []
            IO_Read_BW = []
            Branching_Overhead = []
            IPC = []
            UPI = []
            FLOPc = []
            Retire = []
            Big_Code = []
            Instruction_Fetch_BW = []
            UpTB = []
            IpBranch = []
            Fetch_UpC = []
            DSB_Coverage = []
            DSB_Misses = []
            IpDSB_Miss_Ret = []
            CLKS = []
            Execute_per_Issue = []
            ILP = []
            Execute = []
            FP_Arith_Utilization = []
            Core_Bound_Likely = []
            GFLOPs = []
            IpFLOP = []
            IpArith = [] 
            IpArith_Scalar_SP = []
            IpArith_Scalar_DP = []
            IpArith_AVX128 = []
            IpArith_AVX256 = []
            IpArith_AVX512 = []
            CPU_Utilization = []
            CORE_CLKS = []
            SMT_2T_Utilization = []
            IpLoad = []
            IpStore = []
            IpSWPF = []
            DSB_Switch_Cost = []
            Turbo_Utilization = []
            Power_License0_Utilization = []
            Power_License1_Utilization = []
            Power_License2_Utilization = []
            Kernel_Utilization = []
            Kernel_CPI = []
            IpFarBranch = []
            Time = []
            Socket_CLKS = []

            instance_name = system_conf_fullname(system_conf) + shortname(qps)
            for stat in stats[instance_name]:
                system_stats = stat['server']
                level=int(stats[instance_name].index(stat))%6 + 1
                

                # Level 1
                if level >= 1:
                    Frontend_Bound.extend(sum_perf(system_stats['Frontend_Bound']))
                    Bad_Speculation.extend(sum_perf(system_stats['Bad_Speculation']))
                    Backend_Bound.extend(sum_perf(system_stats['Backend_Bound']))
                    Retiring.extend(sum_perf(system_stats['Retiring']))

                    Frontend_Bound = [i for i in Frontend_Bound if float(i) != 0]
                    Bad_Speculation = [i for i in Bad_Speculation if float(i) != 0]
                    Backend_Bound = [i for i in Backend_Bound if float(i) != 0]
                    Retiring = [i for i in Retiring if float(i) != 0]
                
                # Level 2
                if level >= 2:
                    Frontend_Bound_Fetch_Bandwidth.extend(sum_perf(system_stats['Frontend_Bound_Fetch_Bandwidth']))
                    Frontend_Bound_Fetch_Latency.extend(sum_perf(system_stats['Frontend_Bound_Fetch_Latency']))
                    Bad_Speculation_Branch_Mispredicts.extend(sum_perf(system_stats['Bad_Speculation_Branch_Mispredicts']))
                    Bad_Speculation_Machine_Clears.extend(sum_perf(system_stats['Bad_Speculation_Machine_Clears']))
                    Backend_Bound_Memory_Bound.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound']))
                    Backend_Bound_Core_Bound.extend(sum_perf(system_stats['Backend_Bound_Core_Bound']))
                    Retiring_Heavy_Operations.extend(sum_perf(system_stats['Retiring_Heavy_Operations']))
                    Retiring_Light_Operations.extend(sum_perf(system_stats['Retiring_Light_Operations']))

                    Frontend_Bound_Fetch_Bandwidth = [i for i in Frontend_Bound_Fetch_Bandwidth if float(i) != 0]
                    Frontend_Bound_Fetch_Latency = [i for i in Frontend_Bound_Fetch_Latency if float(i) != 0]
                    Bad_Speculation_Branch_Mispredicts = [i for i in Bad_Speculation_Branch_Mispredicts if float(i) != 0]
                    Bad_Speculation_Machine_Clears = [i for i in Bad_Speculation_Machine_Clears if float(i) != 0]
                    Backend_Bound_Memory_Bound = [i for i in Backend_Bound_Memory_Bound if float(i) != 0]
                    Backend_Bound_Core_Bound = [i for i in Backend_Bound_Core_Bound if float(i) != 0]
                    Retiring_Heavy_Operations = [i for i in Retiring_Heavy_Operations if float(i) != 0]
                    Retiring_Light_Operations = [i for i in Retiring_Light_Operations if float(i) != 0]
                
                # Level 3
                if level >= 3:
                    Frontend_Bound_Fetch_Bandwidth_MITE.extend(sum_perf(system_stats['Frontend_Bound_Fetch_Bandwidth_MITE']))                
                    Frontend_Bound_Fetch_Bandwidth_DSB.extend(sum_perf(system_stats['Frontend_Bound_Fetch_Bandwidth_DSB']))
                    Frontend_Bound_Fetch_Latency_Branch_Resteers.extend(sum_perf(system_stats['Frontend_Bound_Fetch_Latency_Branch_Resteers']))                
                    Frontend_Bound_Fetch_Latency_DSB_Switches.extend(sum_perf(system_stats['Frontend_Bound_Fetch_Latency_DSB_Switches']))
                    Frontend_Bound_Fetch_Latency_ICache_Misses.extend(sum_perf(system_stats['Frontend_Bound_Fetch_Latency_ICache_Misses']))
                    Frontend_Bound_Fetch_Latency_ITLB_Misses.extend(sum_perf(system_stats['Frontend_Bound_Fetch_Latency_ITLB_Misses']))
                    Frontend_Bound_Fetch_Latency_LCP.extend(sum_perf(system_stats['Frontend_Bound_Fetch_Latency_LCP']))
                    Frontend_Bound_Fetch_Latency_MS_Switches.extend(sum_perf(system_stats['Frontend_Bound_Fetch_Latency_MS_Switches']))
                    Backend_Bound_Memory_Bound_DRAM_Bound.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_DRAM_Bound']))               
                    Backend_Bound_Memory_Bound_L1_Bound.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_L1_Bound']))                
                    Backend_Bound_Memory_Bound_L2_Bound.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_L2_Bound']))
                    Backend_Bound_Memory_Bound_L3_Bound.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_L3_Bound']))
                    Backend_Bound_Memory_Bound_Store_Bound.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_Store_Bound']))
                    Backend_Bound_Core_Bound_Divider.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Divider']))
                    Backend_Bound_Core_Bound_Ports_Utilization.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Ports_Utilization']))         
                    Retiring_Heavy_Operations_Few_Uops_Instructions.extend(sum_perf(system_stats['Retiring_Heavy_Operations_Few_Uops_Instructions']))
                    Retiring_Heavy_Operations_Microcode_Sequencer.extend(sum_perf(system_stats['Retiring_Heavy_Operations_Microcode_Sequencer']))
                    Retiring_Light_Operations_FP_Arith.extend(sum_perf(system_stats['Retiring_Light_Operations_FP_Arith']))
                    Retiring_Light_Operations_Fused_Instructions.extend(sum_perf(system_stats['Retiring_Light_Operations_Fused_Instructions']))
                    Retiring_Light_Operations_Memory_Operations.extend(sum_perf(system_stats['Retiring_Light_Operations_Memory_Operations']))
                    Retiring_Light_Operations_Non_Fused_Branches.extend(sum_perf(system_stats['Retiring_Light_Operations_Non_Fused_Branches']))
                    Retiring_Light_Operations_Nop_Instructions.extend(sum_perf(system_stats['Retiring_Light_Operations_Nop_Instructions']))
                            

                    Frontend_Bound_Fetch_Bandwidth_MITE = [i for i in Frontend_Bound_Fetch_Bandwidth_MITE if float(i) != 0]
                    Frontend_Bound_Fetch_Bandwidth_DSB = [i for i in Frontend_Bound_Fetch_Bandwidth_DSB if float(i) != 0]
                    Frontend_Bound_Fetch_Latency_Branch_Resteers = [i for i in Frontend_Bound_Fetch_Latency_Branch_Resteers if float(i) != 0]
                    Frontend_Bound_Fetch_Latency_DSB_Switches = [i for i in Frontend_Bound_Fetch_Latency_DSB_Switches if float(i) != 0]
                    Frontend_Bound_Fetch_Latency_ICache_Misses = [i for i in Frontend_Bound_Fetch_Latency_ICache_Misses if float(i) != 0]
                    Frontend_Bound_Fetch_Latency_ITLB_Misses = [i for i in Frontend_Bound_Fetch_Latency_ITLB_Misses if float(i) != 0]
                    Frontend_Bound_Fetch_Latency_LCP = [i for i in Frontend_Bound_Fetch_Latency_LCP if float(i) != 0]
                    Frontend_Bound_Fetch_Latency_MS_Switches = [i for i in Frontend_Bound_Fetch_Latency_MS_Switches if float(i) != 0]
                    Backend_Bound_Memory_Bound_DRAM_Bound = [i for i in Backend_Bound_Memory_Bound_DRAM_Bound if float(i) != 0]
                    Backend_Bound_Memory_Bound_L1_Bound = [i for i in Backend_Bound_Memory_Bound_L1_Bound if float(i) != 0]
                    Backend_Bound_Memory_Bound_L2_Bound = [i for i in Backend_Bound_Memory_Bound_L2_Bound if float(i) != 0]
                    Backend_Bound_Memory_Bound_L3_Bound = [i for i in Backend_Bound_Memory_Bound_L3_Bound if float(i) != 0]
                    Backend_Bound_Memory_Bound_Store_Bound = [i for i in Backend_Bound_Memory_Bound_Store_Bound if float(i) != 0]
                    Backend_Bound_Core_Bound_Divider = [i for i in Backend_Bound_Core_Bound_Divider if float(i) != 0]
                    Backend_Bound_Core_Bound_Ports_Utilization = [i for i in Backend_Bound_Core_Bound_Ports_Utilization if float(i) != 0]
                    Retiring_Heavy_Operations_Few_Uops_Instructions = [i for i in Retiring_Heavy_Operations_Few_Uops_Instructions if float(i) != 0]
                    Retiring_Heavy_Operations_Microcode_Sequencer = [i for i in Retiring_Heavy_Operations_Microcode_Sequencer if float(i) != 0]
                    Retiring_Light_Operations_FP_Arith = [i for i in Retiring_Light_Operations_FP_Arith if float(i) != 0]
                    Retiring_Light_Operations_Fused_Instructions = [i for i in Retiring_Light_Operations_Fused_Instructions if float(i) != 0]
                    Retiring_Light_Operations_Memory_Operations = [i for i in Retiring_Light_Operations_Memory_Operations if float(i) != 0]
                    Retiring_Light_Operations_Non_Fused_Branches = [i for i in Retiring_Light_Operations_Non_Fused_Branches if float(i) != 0]
                    Retiring_Light_Operations_Nop_Instructions = [i for i in Retiring_Light_Operations_Nop_Instructions if float(i) != 0]
             
                #Level 4
                if level >= 4:
                    Frontend_Bound_Fetch_Latency_Branch_Resteers_Unknown_Branches.extend(sum_perf(system_stats['Frontend_Bound_Fetch_Latency_Branch_Resteers_Unknown_Branches']))
                    Frontend_Bound_Fetch_Latency_Branch_Resteers_Mispredicts_Resteers.extend(sum_perf(system_stats['Frontend_Bound_Fetch_Latency_Branch_Resteers_Mispredicts_Resteers']))
                    Frontend_Bound_Fetch_Latency_Branch_Resteers_Clears_Resteers.extend(sum_perf(system_stats['Frontend_Bound_Fetch_Latency_Branch_Resteers_Clears_Resteers']))
                    Frontend_Bound_Fetch_Bandwidth_MITE_Decoder0_Alone.extend(sum_perf(system_stats['Frontend_Bound_Fetch_Bandwidth_MITE_Decoder0_Alone']))
                    Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load']))
                    Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store']))
                    Backend_Bound_Memory_Bound_L1_Bound_Store_Fwd_Blk.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_L1_Bound_Store_Fwd_Blk']))
                    Backend_Bound_Memory_Bound_L1_Bound_Lock_Latency.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_L1_Bound_Lock_Latency']))
                    Backend_Bound_Memory_Bound_L3_Bound_Contested_Accesses.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_L3_Bound_Contested_Accesses']))
                    Backend_Bound_Memory_Bound_L3_Bound_Data_Sharing.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_L3_Bound_Data_Sharing']))
                    Backend_Bound_Memory_Bound_L3_Bound_SQ_Full.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_L3_Bound_SQ_Full']))
                    Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Bandwidth.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Bandwidth']))
                    Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency']))
                    Backend_Bound_Memory_Bound_Store_Bound_Store_Latency.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_Store_Bound_Store_Latency']))
                    Backend_Bound_Memory_Bound_Store_Bound_False_Sharing.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_Store_Bound_False_Sharing']))
                    Backend_Bound_Memory_Bound_L1_Bound_Split_Loads.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_L1_Bound_Split_Loads']))
                    Backend_Bound_Memory_Bound_L1_Bound_4K_Aliasing.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_L1_Bound_4K_Aliasing']))
                    Backend_Bound_Memory_Bound_L1_Bound_FB_Full.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_L1_Bound_FB_Full']))
                    Backend_Bound_Memory_Bound_L3_Bound_L3_Hit_Latency.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_L3_Bound_L3_Hit_Latency']))
                    Backend_Bound_Memory_Bound_Store_Bound_Split_Stores.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_Store_Bound_Split_Stores']))
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0']))
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_1.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_1']))
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_2.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_2']))
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m']))
                    Retiring_Light_Operations_FP_Arith_X87_Use.extend(sum_perf(system_stats['Retiring_Light_Operations_FP_Arith_X87_Use']))
                    Retiring_Light_Operations_FP_Arith_FP_Scalar.extend(sum_perf(system_stats['Retiring_Light_Operations_FP_Arith_FP_Scalar']))
                    Retiring_Light_Operations_FP_Arith_FP_Vector.extend(sum_perf(system_stats['Retiring_Light_Operations_FP_Arith_FP_Vector']))
                    Retiring_Heavy_Operations_Microcode_Sequencer_Assists.extend(sum_perf(system_stats['Retiring_Heavy_Operations_Microcode_Sequencer_Assists']))
                    Retiring_Heavy_Operations_Microcode_Sequencer_CISC.extend(sum_perf(system_stats['Retiring_Heavy_Operations_Microcode_Sequencer_CISC']))


                    Frontend_Bound_Fetch_Latency_Branch_Resteers_Unknown_Branches  = [i for i in Frontend_Bound_Fetch_Latency_Branch_Resteers_Unknown_Branches if float(i) != 0]
                    Frontend_Bound_Fetch_Latency_Branch_Resteers_Mispredicts_Resteers  = [i for i in Frontend_Bound_Fetch_Latency_Branch_Resteers_Mispredicts_Resteers if float(i) != 0]
                    Frontend_Bound_Fetch_Latency_Branch_Resteers_Clears_Resteers  = [i for i in Frontend_Bound_Fetch_Latency_Branch_Resteers_Clears_Resteers if float(i) != 0]
                    Frontend_Bound_Fetch_Bandwidth_MITE_Decoder0_Alone  = [i for i in Frontend_Bound_Fetch_Bandwidth_MITE_Decoder0_Alone if float(i) != 0]
                    Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load  = [i for i in Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load if float(i) != 0]
                    Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store  = [i for i in Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store if float(i) != 0]
                    Backend_Bound_Memory_Bound_L1_Bound_Store_Fwd_Blk  = [i for i in Backend_Bound_Memory_Bound_L1_Bound_Store_Fwd_Blk if float(i) != 0]
                    Backend_Bound_Memory_Bound_L1_Bound_Lock_Latency  = [i for i in Backend_Bound_Memory_Bound_L1_Bound_Lock_Latency if float(i) != 0]
                    Backend_Bound_Memory_Bound_L3_Bound_Contested_Accesses  = [i for i in Backend_Bound_Memory_Bound_L3_Bound_Contested_Accesses if float(i) != 0]
                    Backend_Bound_Memory_Bound_L3_Bound_Data_Sharing  = [i for i in Backend_Bound_Memory_Bound_L3_Bound_Data_Sharing if float(i) != 0]
                    Backend_Bound_Memory_Bound_L3_Bound_SQ_Full  = [i for i in Backend_Bound_Memory_Bound_L3_Bound_SQ_Full if float(i) != 0]
                    Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Bandwidth  = [i for i in Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Bandwidth if float(i) != 0]
                    Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency  = [i for i in Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency if float(i) != 0]
                    Backend_Bound_Memory_Bound_Store_Bound_Store_Latency  = [i for i in Backend_Bound_Memory_Bound_Store_Bound_Store_Latency if float(i) != 0]
                    Backend_Bound_Memory_Bound_Store_Bound_False_Sharing  = [i for i in Backend_Bound_Memory_Bound_Store_Bound_False_Sharing if float(i) != 0]
                    Backend_Bound_Memory_Bound_L1_Bound_Split_Loads  = [i for i in Backend_Bound_Memory_Bound_L1_Bound_Split_Loads if float(i) != 0]
                    Backend_Bound_Memory_Bound_L1_Bound_4K_Aliasing  = [i for i in Backend_Bound_Memory_Bound_L1_Bound_4K_Aliasing if float(i) != 0]
                    Backend_Bound_Memory_Bound_L1_Bound_FB_Full  = [i for i in Backend_Bound_Memory_Bound_L1_Bound_FB_Full if float(i) != 0]
                    Backend_Bound_Memory_Bound_L3_Bound_L3_Hit_Latency  = [i for i in Backend_Bound_Memory_Bound_L3_Bound_L3_Hit_Latency if float(i) != 0]
                    Backend_Bound_Memory_Bound_Store_Bound_Split_Stores  = [i for i in Backend_Bound_Memory_Bound_Store_Bound_Split_Stores if float(i) != 0]
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0  = [i for i in Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0 if float(i) != 0]
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_1  = [i for i in Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_1 if float(i) != 0]
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_2  = [i for i in Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_2 if float(i) != 0]
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m  = [i for i in Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m if float(i) != 0]
                    Retiring_Light_Operations_FP_Arith_X87_Use  = [i for i in Retiring_Light_Operations_FP_Arith_X87_Use if float(i) != 0]
                    Retiring_Light_Operations_FP_Arith_FP_Scalar  = [i for i in Retiring_Light_Operations_FP_Arith_FP_Scalar if float(i) != 0]
                    Retiring_Light_Operations_FP_Arith_FP_Vector  = [i for i in Retiring_Light_Operations_FP_Arith_FP_Vector if float(i) != 0]
                    Retiring_Heavy_Operations_Microcode_Sequencer_Assists  = [i for i in Retiring_Heavy_Operations_Microcode_Sequencer_Assists if float(i) != 0]
                    Retiring_Heavy_Operations_Microcode_Sequencer_CISC  = [i for i in Retiring_Heavy_Operations_Microcode_Sequencer_CISC if float(i) != 0]

                #Level 5
                if level >= 5:
                    Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Hit.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Hit']))
                    Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Miss.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Miss']))
                    Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Hit.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Hit']))
                    Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Miss.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Miss']))
                    Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_Cache.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_Cache']))
                    Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Local_DRAM.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Local_DRAM']))
                    Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_DRAM.extend(sum_perf(system_stats['Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_DRAM']))
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Serializing_Operation.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Serializing_Operation']))
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Mixing_Vectors.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Mixing_Vectors']))
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization']))
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization']))
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization']))
                    Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_128b.extend(sum_perf(system_stats['Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_128b']))
                    Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_256b.extend(sum_perf(system_stats['Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_256b']))
                    Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_512b.extend(sum_perf(system_stats['Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_512b']))



                    Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Hit  = [i for i in Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Hit if float(i) != 0]
                    Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Miss  = [i for i in Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Miss if float(i) != 0]
                    Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Hit  = [i for i in Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Hit if float(i) != 0]
                    Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Miss  = [i for i in Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Miss if float(i) != 0]
                    Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_Cache  = [i for i in Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_Cache if float(i) != 0]
                    Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Local_DRAM  = [i for i in Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Local_DRAM if float(i) != 0]
                    Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_DRAM  = [i for i in Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_DRAM if float(i) != 0]
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Serializing_Operation  = [i for i in Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Serializing_Operation if float(i) != 0]
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Mixing_Vectors  = [i for i in Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Mixing_Vectors if float(i) != 0]
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization  = [i for i in Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization if float(i) != 0]
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization  = [i for i in Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization if float(i) != 0]
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization  = [i for i in Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization if float(i) != 0]
                    Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_128b = [i for i in Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_128b if float(i) != 0]
                    Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_256b = [i for i in Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_256b if float(i) != 0]
                    Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_512b  = [i for i in Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_512b if float(i) != 0]


                #Level 6
                if level >= 6:
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_0.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_0']))
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_1.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_1']))
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_5.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_5']))
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_6.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_6']))
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_2.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_2']))
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_3.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_3']))
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_4.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_4']))
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_7.extend(sum_perf(system_stats['Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_7']))

                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_0  = [i for i in Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_0 if float(i) != 0]
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_1  = [i for i in Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_1 if float(i) != 0]
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_5  = [i for i in Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_5 if float(i) != 0]
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_6  = [i for i in Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_6 if float(i) != 0]
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_2  = [i for i in Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_2 if float(i) != 0]
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_3  = [i for i in Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_3 if float(i) != 0]
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_4  = [i for i in Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_4 if float(i) != 0]
                    Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_7  = [i for i in Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_7 if float(i) != 0]


                #metrics
                SLOTS.extend(sum_perf(system_stats['SLOTS']))
                CoreIPC.extend(sum_perf(system_stats['CoreIPC']))
                Instructions.extend(sum_perf(system_stats['Instructions']))
                IpCall.extend(sum_perf(system_stats['IpCall']))
                IpTB.extend(sum_perf(system_stats['IpTB']))
                BpTkBranch.extend(sum_perf(system_stats['BpTkBranch']))
                Cond_NT.extend(sum_perf(system_stats['Cond_NT']))
                Cond_TK.extend(sum_perf(system_stats['Cond_TK']))
                Mispredictions.extend(sum_perf(system_stats['Mispredictions']))
                IpMispredict.extend(sum_perf(system_stats['IpMispredict']))
                Branch_Misprediction_Cost.extend(sum_perf(system_stats['Branch_Misprediction_Cost']))
                CallRet.extend(sum_perf(system_stats['CallRet']))
                Jump.extend(sum_perf(system_stats['Jump']))
                Memory_Bandwidth.extend(sum_perf(system_stats['Memory_Bandwidth']))
                Memory_Latency.extend(sum_perf(system_stats['Memory_Latency']))
                Memory_Data_TLBs.extend(sum_perf(system_stats['Memory_Data_TLBs']))
                CPI.extend(sum_perf(system_stats['CPI']))
                Load_Miss_Real_Latency.extend(sum_perf(system_stats['Load_Miss_Real_Latency']))
                MLP.extend(sum_perf(system_stats['MLP']))
                L1MPKI.extend(sum_perf(system_stats['L1MPKI']))
                L1MPKI_Load.extend(sum_perf(system_stats['L1MPKI_Load']))
                L2MPKI.extend(sum_perf(system_stats['L2MPKI']))
                L2MPKI_All.extend(sum_perf(system_stats['L2MPKI_All']))
                L2MPKI_Load.extend(sum_perf(system_stats['L2MPKI_Load']))
                L2HPKI_All.extend(sum_perf(system_stats['L2HPKI_All']))
                L2HPKI_Load.extend(sum_perf(system_stats['L2HPKI_Load']))
                L3MPKI.extend(sum_perf(system_stats['L3MPKI']))
                FB_HPKI.extend(sum_perf(system_stats['FB_HPKI']))
                Page_Walks_Utilization.extend(sum_perf(system_stats['Page_Walks_Utilization']))
                L1D_Cache_Fill_BW.extend(sum_perf(system_stats['L1D_Cache_Fill_BW']))
                L2_Cache_Fill_BW.extend(sum_perf(system_stats['L2_Cache_Fill_BW']))
                L3_Cache_Fill_BW.extend(sum_perf(system_stats['L3_Cache_Fill_BW']))
                L3_Cache_Access_BW.extend(sum_perf(system_stats['L3_Cache_Access_BW']))
                L2_Evictions_Silent_PKI.extend(sum_perf(system_stats['L2_Evictions_Silent_PKI']))
                L2_Evictions_NonSilent_PKI.extend(sum_perf(system_stats['L2_Evictions_NonSilent_PKI']))
                L1D_Cache_Fill_BW_1T.extend(sum_perf(system_stats['L1D_Cache_Fill_BW_1T']))
                L2_Cache_Fill_BW_1T.extend(sum_perf(system_stats['L2_Cache_Fill_BW_1T']))
                L3_Cache_Fill_BW_1T.extend(sum_perf(system_stats['L3_Cache_Fill_BW_1T']))
                L3_Cache_Access_BW_1T.extend(sum_perf(system_stats['L3_Cache_Access_BW_1T']))
                DRAM_BW_Use.extend(sum_perf(system_stats['DRAM_BW_Use']))
                MEM_Read_Latency.extend(sum_perf(system_stats['MEM_Read_Latency']))
                MEM_DRAM_Read_Latency.extend(sum_perf(system_stats['MEM_DRAM_Read_Latency']))
                IO_Write_BW.extend(sum_perf(system_stats['IO_Write_BW']))
                IO_Read_BW.extend(sum_perf(system_stats['IO_Read_BW']))
                Branching_Overhead.extend(sum_perf(system_stats['Branching_Overhead']))
                IPC.extend(sum_perf(system_stats['IPC']))
                UPI.extend(sum_perf(system_stats['UPI']))
                FLOPc.extend(sum_perf(system_stats['FLOPc']))
                Retire.extend(sum_perf(system_stats['Retire']))
                Big_Code.extend(sum_perf(system_stats['Big_Code']))
                Instruction_Fetch_BW.extend(sum_perf(system_stats['Instruction_Fetch_BW']))
                UpTB.extend(sum_perf(system_stats['UpTB']))
                IpBranch.extend(sum_perf(system_stats['IpBranch']))
                Fetch_UpC.extend(sum_perf(system_stats['Fetch_UpC']))
                DSB_Coverage.extend(sum_perf(system_stats['DSB_Coverage']))
                DSB_Misses.extend(sum_perf(system_stats['DSB_Misses']))
                IpDSB_Miss_Ret.extend(sum_perf(system_stats['IpDSB_Miss_Ret']))
                CLKS.extend(sum_perf(system_stats['CLKS']))
                Execute_per_Issue.extend(sum_perf(system_stats['Execute_per_Issue']))
                ILP.extend(sum_perf(system_stats['ILP']))
                Execute.extend(sum_perf(system_stats['Execute']))
                FP_Arith_Utilization.extend(sum_perf(system_stats['FP_Arith_Utilization']))
                Core_Bound_Likely.extend(sum_perf(system_stats['Core_Bound_Likely']))
                GFLOPs.extend(sum_perf(system_stats['GFLOPs']))
                IpFLOP.extend(sum_perf(system_stats['IpFLOP']))
                IpArith.extend(sum_perf(system_stats['IpArith']))
                IpArith_Scalar_SP.extend(sum_perf(system_stats['IpArith_Scalar_SP']))
                IpArith_Scalar_DP.extend(sum_perf(system_stats['IpArith_Scalar_DP']))
                IpArith_AVX128.extend(sum_perf(system_stats['IpArith_AVX128']))
                IpArith_AVX256.extend(sum_perf(system_stats['IpArith_AVX256']))
                IpArith_AVX512.extend(sum_perf(system_stats['IpArith_AVX512']))
                CPU_Utilization.extend(sum_perf(system_stats['CPU_Utilization']))
                CORE_CLKS.extend(sum_perf(system_stats['CORE_CLKS']))
                SMT_2T_Utilization.extend(sum_perf(system_stats['SMT_2T_Utilization']))
                IpLoad.extend(sum_perf(system_stats['IpLoad']))
                IpStore.extend(sum_perf(system_stats['IpStore']))
                IpSWPF.extend(sum_perf(system_stats['IpSWPF']))
                DSB_Switch_Cost.extend(sum_perf(system_stats['DSB_Switch_Cost']))
                Turbo_Utilization.extend(sum_perf(system_stats['Turbo_Utilization']))
                Power_License0_Utilization.extend(sum_perf(system_stats['Power_License0_Utilization']))
                Power_License1_Utilization.extend(sum_perf(system_stats['Power_License1_Utilization']))
                Power_License2_Utilization.extend(sum_perf(system_stats['Power_License2_Utilization']))
                Kernel_Utilization.extend(sum_perf(system_stats['Kernel_Utilization']))
                Kernel_CPI.extend(sum_perf(system_stats['Kernel_CPI']))
                IpFarBranch.extend(sum_perf(system_stats['IpFarBranch']))
                Time.extend(sum_perf(system_stats['Time']))
                Socket_CLKS.extend(sum_perf(system_stats['Socket_CLKS']))

                SLOTS  = [i for i in SLOTS if float(i) != 0]
                CoreIPC  = [i for i in CoreIPC if float(i) != 0]
                Instructions  = [i for i in Instructions if float(i) != 0]
                IpCall  = [i for i in IpCall if float(i) != 0]
                IpTB  = [i for i in IpTB if float(i) != 0]
                BpTkBranch  = [i for i in BpTkBranch if float(i) != 0]
                Cond_NT  = [i for i in Cond_NT if float(i) != 0]
                Cond_TK  = [i for i in Cond_TK if float(i) != 0]
                Mispredictions  = [i for i in Mispredictions if float(i) != 0]
                IpMispredict  = [i for i in IpMispredict if float(i) != 0]
                Branch_Misprediction_Cost  = [i for i in Branch_Misprediction_Cost if float(i) != 0]
                CallRet  = [i for i in CallRet if float(i) != 0]
                Jump  = [i for i in Jump if float(i) != 0]
                Memory_Bandwidth  = [i for i in Memory_Bandwidth if float(i) != 0]
                Memory_Latency  = [i for i in Memory_Latency if float(i) != 0]
                Memory_Data_TLBs  = [i for i in Memory_Data_TLBs if float(i) != 0]
                CPI  = [i for i in CPI if float(i) != 0]
                Load_Miss_Real_Latency  = [i for i in Load_Miss_Real_Latency if float(i) != 0]
                MLP  = [i for i in MLP if float(i) != 0]
                L1MPKI  = [i for i in L1MPKI if float(i) != 0]
                L1MPKI_Load  = [i for i in L1MPKI_Load if float(i) != 0]
                L2MPKI  = [i for i in L2MPKI if float(i) != 0]
                L2MPKI_All  = [i for i in L2MPKI_All if float(i) != 0]
                L2MPKI_Load  = [i for i in L2MPKI_Load if float(i) != 0]
                L2HPKI_All  = [i for i in L2HPKI_All if float(i) != 0]
                L2HPKI_Load  = [i for i in L2HPKI_Load if float(i) != 0]
                L3MPKI  = [i for i in L3MPKI if float(i) != 0]
                FB_HPKI  = [i for i in FB_HPKI if float(i) != 0]
                Page_Walks_Utilization = [i for i in Page_Walks_Utilization if float(i) != 0]
                L1D_Cache_Fill_BW = [i for i in L1D_Cache_Fill_BW if float(i) != 0]
                L2_Cache_Fill_BW = [i for i in L2_Cache_Fill_BW if float(i) != 0]
                L3_Cache_Fill_BW = [i for i in L3_Cache_Fill_BW if float(i) != 0]
                L3_Cache_Access_BW = [i for i in L3_Cache_Access_BW if float(i) != 0]
                L2_Evictions_Silent_PKI = [i for i in L2_Evictions_Silent_PKI if float(i) != 0]
                L2_Evictions_NonSilent_PKI = [i for i in L2_Evictions_NonSilent_PKI if float(i) != 0]
                L1D_Cache_Fill_BW_1T = [i for i in L1D_Cache_Fill_BW_1T if float(i) != 0]
                L2_Cache_Fill_BW_1T = [i for i in L2_Cache_Fill_BW_1T if float(i) != 0]
                L3_Cache_Fill_BW_1T = [i for i in L3_Cache_Fill_BW_1T if float(i) != 0]
                L3_Cache_Access_BW_1T = [i for i in L3_Cache_Access_BW_1T if float(i) != 0]
                DRAM_BW_Use = [i for i in DRAM_BW_Use if float(i) != 0]
                MEM_Read_Latency = [i for i in MEM_Read_Latency if float(i) != 0]
                MEM_DRAM_Read_Latency = [i for i in MEM_DRAM_Read_Latency if float(i) != 0]
                IO_Write_BW = [i for i in IO_Write_BW if float(i) != 0]
                IO_Read_BW = [i for i in IO_Read_BW if float(i) != 0]
                Branching_Overhead = [i for i in Branching_Overhead if float(i) != 0]
                IPC = [i for i in IPC if float(i) != 0]
                UPI = [i for i in UPI if float(i) != 0]
                FLOPc = [i for i in FLOPc if float(i) != 0]
                Retire = [i for i in Retire if float(i) != 0]
                Big_Code = [i for i in Big_Code if float(i) != 0]
                Instruction_Fetch_BW = [i for i in Instruction_Fetch_BW if float(i) != 0]
                UpTB = [i for i in UpTB if float(i) != 0]
                IpBranch = [i for i in IpBranch if float(i) != 0]
                Fetch_UpC = [i for i in Fetch_UpC if float(i) != 0]
                DSB_Coverage = [i for i in DSB_Coverage if float(i) != 0]
                DSB_Misses = [i for i in DSB_Misses if float(i) != 0]
                IpDSB_Miss_Ret = [i for i in IpDSB_Miss_Ret if float(i) != 0]
                CLKS = [i for i in CLKS if float(i) != 0]
                Execute_per_Issue = [i for i in Execute_per_Issue if float(i) != 0]
                ILP = [i for i in ILP if float(i) != 0]
                Execute = [i for i in Execute if float(i) != 0]
                FP_Arith_Utilization = [i for i in FP_Arith_Utilization if float(i) != 0]
                Core_Bound_Likely = [i for i in Core_Bound_Likely if float(i) != 0]
                GFLOPs = [i for i in GFLOPs if float(i) != 0]
                IpFLOP = [i for i in IpFLOP if float(i) != 0]
                IpArith = [i for i in IpArith if float(i) != 0] 
                IpArith_Scalar_SP = [i for i in IpArith_Scalar_SP if float(i) != 0]
                IpArith_Scalar_DP = [i for i in IpArith_Scalar_DP if float(i) != 0]
                IpArith_AVX128 = [i for i in IpArith_AVX128 if float(i) != 0]
                IpArith_AVX256 = [i for i in IpArith_AVX256 if float(i) != 0]
                IpArith_AVX512 = [i for i in IpArith_AVX512 if float(i) != 0]
                CPU_Utilization = [i for i in CPU_Utilization if float(i) != 0]
                CORE_CLKS = [i for i in CORE_CLKS if float(i) != 0]
                SMT_2T_Utilization = [i for i in SMT_2T_Utilization if float(i) != 0]
                IpLoad = [i for i in IpLoad if float(i) != 0]
                IpStore = [i for i in IpStore if float(i) != 0]
                IpSWPF = [i for i in IpSWPF if float(i) != 0]
                DSB_Switch_Cost = [i for i in DSB_Switch_Cost if float(i) != 0]
                Turbo_Utilization = [i for i in Turbo_Utilization if float(i) != 0]
                Power_License0_Utilization = [i for i in Power_License0_Utilization if float(i) != 0]
                Power_License1_Utilization = [i for i in Power_License1_Utilization if float(i) != 0]
                Power_License2_Utilization = [i for i in Power_License2_Utilization if float(i) != 0]
                Kernel_Utilization = [i for i in Kernel_Utilization if float(i) != 0]
                Kernel_CPI = [i for i in Kernel_CPI if float(i) != 0]
                IpFarBranch = [i for i in IpFarBranch if float(i) != 0]
                Time = [i for i in Time if float(i) != 0]
                Socket_CLKS = [i for i in Socket_CLKS if float(i) != 0]


            # Level 1             
            row.append(str(float(statistics.mean(Frontend_Bound))) if len(Frontend_Bound) > 1 else '0')
            row.append(str(float(statistics.mean(Bad_Speculation))) if len(Bad_Speculation) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound))) if len(Backend_Bound) > 1 else '0')
            row.append(str(float(statistics.mean(Retiring))) if len(Retiring) > 1 else '0')
            
            # Level 2
            row.append(str(float(statistics.mean(Frontend_Bound_Fetch_Bandwidth))) if len(Frontend_Bound_Fetch_Bandwidth) > 1 else '0')
            row.append(str(float(statistics.mean(Frontend_Bound_Fetch_Latency))) if len(Frontend_Bound_Fetch_Latency) > 1 else '0')
            row.append(str(float(statistics.mean(Bad_Speculation_Branch_Mispredicts))) if len(Bad_Speculation_Branch_Mispredicts) > 1 else '0')
            row.append(str(float(statistics.mean(Bad_Speculation_Machine_Clears))) if len(Bad_Speculation_Machine_Clears) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound))) if len(Backend_Bound_Memory_Bound) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound))) if len(Backend_Bound_Core_Bound) > 1 else '0')
            row.append(str(float(statistics.mean(Retiring_Heavy_Operations))) if len(Retiring_Heavy_Operations) > 1 else '0')
            row.append(str(float(statistics.mean(Retiring_Light_Operations))) if len(Retiring_Light_Operations) > 1 else '0')
            
            # Level 3
            row.append(str(float(statistics.mean(Frontend_Bound_Fetch_Bandwidth_MITE))) if len(Frontend_Bound_Fetch_Bandwidth_MITE) > 1 else '0')
            row.append(str(float(statistics.mean(Frontend_Bound_Fetch_Bandwidth_DSB))) if len(Frontend_Bound_Fetch_Bandwidth_DSB) > 1 else '0')
            row.append(str(float(statistics.mean(Frontend_Bound_Fetch_Latency_Branch_Resteers))) if len(Frontend_Bound_Fetch_Latency_Branch_Resteers) > 1 else '0')
            row.append(str(float(statistics.mean(Frontend_Bound_Fetch_Latency_DSB_Switches))) if len(Frontend_Bound_Fetch_Latency_DSB_Switches) > 1 else '0')
            row.append(str(float(statistics.mean(Frontend_Bound_Fetch_Latency_ICache_Misses))) if len(Frontend_Bound_Fetch_Latency_ICache_Misses) > 1 else '0')
            row.append(str(float(statistics.mean(Frontend_Bound_Fetch_Latency_ITLB_Misses))) if len(Frontend_Bound_Fetch_Latency_ITLB_Misses) > 1 else '0')
            row.append(str(float(statistics.mean(Frontend_Bound_Fetch_Latency_LCP))) if len(Frontend_Bound_Fetch_Latency_LCP) > 1 else '0')
            row.append(str(float(statistics.mean(Frontend_Bound_Fetch_Latency_MS_Switches))) if len(Frontend_Bound_Fetch_Latency_MS_Switches) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_DRAM_Bound))) if len(Backend_Bound_Memory_Bound_DRAM_Bound) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_L1_Bound))) if len(Backend_Bound_Memory_Bound_L1_Bound) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_L2_Bound))) if len(Backend_Bound_Memory_Bound_L2_Bound) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_L3_Bound))) if len(Backend_Bound_Memory_Bound_L3_Bound) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_Store_Bound))) if len(Backend_Bound_Memory_Bound_Store_Bound) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Divider))) if len(Backend_Bound_Core_Bound_Divider) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Ports_Utilization))) if len(Backend_Bound_Core_Bound_Ports_Utilization) > 1 else '0')
            row.append(str(float(statistics.mean(Retiring_Heavy_Operations_Few_Uops_Instructions))) if len(Retiring_Heavy_Operations_Few_Uops_Instructions) > 1 else '0')
            row.append(str(float(statistics.mean(Retiring_Heavy_Operations_Microcode_Sequencer))) if len(Retiring_Heavy_Operations_Microcode_Sequencer) > 1 else '0')
            row.append(str(float(statistics.mean(Retiring_Light_Operations_FP_Arith))) if len(Retiring_Light_Operations_FP_Arith) > 1 else '0')
            row.append(str(float(statistics.mean(Retiring_Light_Operations_Fused_Instructions))) if len(Retiring_Light_Operations_Fused_Instructions) > 1 else '0')
            row.append(str(float(statistics.mean(Retiring_Light_Operations_Memory_Operations))) if len(Retiring_Light_Operations_Memory_Operations) > 1 else '0')
            row.append(str(float(statistics.mean(Retiring_Light_Operations_Non_Fused_Branches))) if len(Retiring_Light_Operations_Non_Fused_Branches) > 1 else '0')
            row.append(str(float(statistics.mean(Retiring_Light_Operations_Nop_Instructions))) if len(Retiring_Light_Operations_Nop_Instructions) > 1 else '0')
 

            #Level 4
            row.append(str(float(statistics.mean(Frontend_Bound_Fetch_Latency_Branch_Resteers_Unknown_Branches))) if len(Frontend_Bound_Fetch_Latency_Branch_Resteers_Unknown_Branches) > 1 else '0')
            row.append(str(float(statistics.mean(Frontend_Bound_Fetch_Latency_Branch_Resteers_Mispredicts_Resteers))) if len(Frontend_Bound_Fetch_Latency_Branch_Resteers_Mispredicts_Resteers) > 1 else '0')
            row.append(str(float(statistics.mean(Frontend_Bound_Fetch_Latency_Branch_Resteers_Clears_Resteers))) if len(Frontend_Bound_Fetch_Latency_Branch_Resteers_Clears_Resteers) > 1 else '0')
            row.append(str(float(statistics.mean(Frontend_Bound_Fetch_Bandwidth_MITE_Decoder0_Alone))) if len(Frontend_Bound_Fetch_Bandwidth_MITE_Decoder0_Alone) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load))) if len(Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store))) if len(Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_L1_Bound_Store_Fwd_Blk))) if len(Backend_Bound_Memory_Bound_L1_Bound_Store_Fwd_Blk) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_L1_Bound_Lock_Latency))) if len(Backend_Bound_Memory_Bound_L1_Bound_Lock_Latency) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_L3_Bound_Contested_Accesses))) if len(Backend_Bound_Memory_Bound_L3_Bound_Contested_Accesses) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_L3_Bound_Data_Sharing))) if len(Backend_Bound_Memory_Bound_L3_Bound_Data_Sharing) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_L3_Bound_SQ_Full))) if len(Backend_Bound_Memory_Bound_L3_Bound_SQ_Full) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Bandwidth))) if len(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Bandwidth) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency))) if len(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_Store_Bound_Store_Latency))) if len(Backend_Bound_Memory_Bound_Store_Bound_Store_Latency) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_Store_Bound_False_Sharing))) if len(Backend_Bound_Memory_Bound_Store_Bound_False_Sharing) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_L1_Bound_Split_Loads))) if len(Backend_Bound_Memory_Bound_L1_Bound_Split_Loads) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_L1_Bound_4K_Aliasing))) if len(Backend_Bound_Memory_Bound_L1_Bound_4K_Aliasing) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_L1_Bound_FB_Full))) if len(Backend_Bound_Memory_Bound_L1_Bound_FB_Full) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_L3_Bound_L3_Hit_Latency))) if len(Backend_Bound_Memory_Bound_L3_Bound_L3_Hit_Latency) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_Store_Bound_Split_Stores))) if len(Backend_Bound_Memory_Bound_Store_Bound_Split_Stores) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_1)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_1) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_2)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_2) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m) > 1 else '0')
            row.append(str(float(statistics.mean(Retiring_Light_Operations_FP_Arith_X87_Use)))  if len(Retiring_Light_Operations_FP_Arith_X87_Use) > 1 else '0')
            row.append(str(float(statistics.mean(Retiring_Light_Operations_FP_Arith_FP_Scalar)))  if len(Retiring_Light_Operations_FP_Arith_FP_Scalar) > 1 else '0')
            row.append(str(float(statistics.mean(Retiring_Light_Operations_FP_Arith_FP_Vector)))  if len(Retiring_Light_Operations_FP_Arith_FP_Vector) > 1 else '0')
            row.append(str(float(statistics.mean(Retiring_Heavy_Operations_Microcode_Sequencer_Assists)))  if len(Retiring_Heavy_Operations_Microcode_Sequencer_Assists) > 1 else '0')
            row.append(str(float(statistics.mean(Retiring_Heavy_Operations_Microcode_Sequencer_CISC)))  if len(Retiring_Heavy_Operations_Microcode_Sequencer_CISC) > 1 else '0')

            #Level 5
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Hit)))  if len(Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Hit) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Miss)))  if len(Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Miss) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Hit)))  if len(Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Hit) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Miss)))  if len(Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Miss) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_Cache)))  if len(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_Cache) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Local_DRAM)))  if len(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Local_DRAM) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_DRAM)))  if len(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_DRAM) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Serializing_Operation))) if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Serializing_Operation) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Mixing_Vectors)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Mixing_Vectors) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization) > 1 else '0')
            row.append(str(float(statistics.mean(Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_128b))) if len(Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_128b) > 1 else '0')
            row.append(str(float(statistics.mean(Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_256b))) if len(Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_256b) > 1 else '0')
            row.append(str(float(statistics.mean(Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_512b)))  if len(Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_512b) > 1 else '0')


            #Level 6
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_0)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_0) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_1)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_1) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_5)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_5) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_6)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_6) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_2)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_2) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_3)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_3) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_4)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_4) > 1 else '0')
            row.append(str(float(statistics.mean(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_7)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_7) > 1 else '0')


            #metrics

            row.append(str(float(statistics.mean(SLOTS)))  if len(SLOTS) > 1 else '0')
            row.append(str(float(statistics.mean(CoreIPC)))  if len(CoreIPC) > 1 else '0')
            row.append(str(float(statistics.mean(Instructions)))  if len(Instructions) > 1 else '0')
            row.append(str(float(statistics.mean(IpCall)))  if len(IpCall) > 1 else '0')
            row.append(str(float(statistics.mean(IpTB)))  if len(IpTB) > 1 else '0')
            row.append(str(float(statistics.mean(BpTkBranch)))  if len(BpTkBranch) > 1 else '0')
            row.append(str(float(statistics.mean(Cond_NT)))  if len(Cond_NT) > 1 else '0')
            row.append(str(float(statistics.mean(Cond_TK)))  if len(Cond_TK) > 1 else '0')
            row.append(str(float(statistics.mean(Mispredictions)))  if len(Mispredictions) > 1 else '0')
            row.append(str(float(statistics.mean(IpMispredict)))  if len(IpMispredict) > 1 else '0')
            row.append(str(float(statistics.mean(Branch_Misprediction_Cost)))  if len(Branch_Misprediction_Cost) > 1 else '0')
            row.append(str(float(statistics.mean(CallRet)))  if len(CallRet) > 1 else '0')
            row.append(str(float(statistics.mean(Jump)))  if len(Jump) > 1 else '0')
            row.append(str(float(statistics.mean(Memory_Bandwidth)))  if len(Memory_Bandwidth) > 1 else '0')
            row.append(str(float(statistics.mean(Memory_Latency)))  if len(Memory_Latency) > 1 else '0')
            row.append(str(float(statistics.mean(Memory_Data_TLBs)))  if len(Memory_Data_TLBs) > 1 else '0')
            row.append(str(float(statistics.mean(CPI)))  if len(CPI) > 1 else '0')
            row.append(str(float(statistics.mean(Load_Miss_Real_Latency)))  if len(Load_Miss_Real_Latency) > 1 else '0')
            row.append(str(float(statistics.mean(MLP)))  if len(MLP) > 1 else '0')
            row.append(str(float(statistics.mean(L1MPKI)))  if len(L1MPKI) > 1 else '0')
            row.append(str(float(statistics.mean(L1MPKI_Load)))  if len(L1MPKI_Load) > 1 else '0')
            row.append(str(float(statistics.mean(L2MPKI)))  if len(L2MPKI) > 1 else '0')
            row.append(str(float(statistics.mean(L2MPKI_All)))  if len(L2MPKI_All) > 1 else '0')
            row.append(str(float(statistics.mean(L2MPKI_Load)))  if len(L2MPKI_Load) > 1 else '0')
            row.append(str(float(statistics.mean(L2HPKI_All)))  if len(L2HPKI_All) > 1 else '0')
            row.append(str(float(statistics.mean(L2HPKI_Load)))  if len(L2HPKI_Load) > 1 else '0')
            row.append(str(float(statistics.mean(L3MPKI)))  if len(L3MPKI) > 1 else '0')
            row.append(str(float(statistics.mean(FB_HPKI)))  if len(FB_HPKI) > 1 else '0')
            row.append(str(float(statistics.mean(Page_Walks_Utilization)))  if len(Page_Walks_Utilization) > 1 else '0')
            row.append(str(float(statistics.mean(L1D_Cache_Fill_BW)))  if len(L1D_Cache_Fill_BW) > 1 else '0')
            row.append(str(float(statistics.mean(L2_Cache_Fill_BW)))  if len(L2_Cache_Fill_BW) > 1 else '0')
            row.append(str(float(statistics.mean(L3_Cache_Fill_BW)))  if len(L3_Cache_Fill_BW) > 1 else '0')
            row.append(str(float(statistics.mean(L3_Cache_Access_BW)))  if len(L3_Cache_Access_BW) > 1 else '0')
            row.append(str(float(statistics.mean(L2_Evictions_Silent_PKI)))  if len(L2_Evictions_Silent_PKI) > 1 else '0')
            row.append(str(float(statistics.mean(L2_Evictions_NonSilent_PKI)))  if len(L2_Evictions_NonSilent_PKI) > 1 else '0')
            row.append(str(float(statistics.mean(L1D_Cache_Fill_BW_1T)))  if len(L1D_Cache_Fill_BW_1T) > 1 else '0')
            row.append(str(float(statistics.mean(L2_Cache_Fill_BW_1T)))  if len(L2_Cache_Fill_BW_1T) > 1 else '0')
            row.append(str(float(statistics.mean(L3_Cache_Fill_BW_1T)))  if len(L3_Cache_Fill_BW_1T) > 1 else '0')
            row.append(str(float(statistics.mean(L3_Cache_Access_BW_1T)))  if len(L3_Cache_Access_BW_1T) > 1 else '0')
            row.append(str(float(statistics.mean(DRAM_BW_Use)))  if len(DRAM_BW_Use) > 1 else '0')
            row.append(str(float(statistics.mean(MEM_Read_Latency)))  if len(MEM_Read_Latency) > 1 else '0')
            row.append(str(float(statistics.mean(MEM_DRAM_Read_Latency)))  if len(MEM_DRAM_Read_Latency) > 1 else '0')
            row.append(str(float(statistics.mean(IO_Write_BW)))  if len(IO_Write_BW) > 1 else '0')
            row.append(str(float(statistics.mean(IO_Read_BW)))  if len(IO_Read_BW) > 1 else '0')
            row.append(str(float(statistics.mean(Branching_Overhead)))  if len(Branching_Overhead) > 1 else '0')
            row.append(str(float(statistics.mean(IPC)))  if len(IPC) > 1 else '0')
            row.append(str(float(statistics.mean(UPI)))  if len(UPI) > 1 else '0')
            row.append(str(float(statistics.mean(FLOPc)))  if len(FLOPc) > 1 else '0')
            row.append(str(float(statistics.mean(Retire)))  if len(Retire) > 1 else '0')
            row.append(str(float(statistics.mean(Big_Code)))  if len(Big_Code) > 1 else '0')
            row.append(str(float(statistics.mean(Instruction_Fetch_BW)))  if len(Instruction_Fetch_BW) > 1 else '0')
            row.append(str(float(statistics.mean(UpTB)))  if len(UpTB) > 1 else '0')
            row.append(str(float(statistics.mean(IpBranch)))  if len(IpBranch) > 1 else '0')
            row.append(str(float(statistics.mean(Fetch_UpC)))  if len(Fetch_UpC) > 1 else '0')
            row.append(str(float(statistics.mean(DSB_Coverage)))  if len(DSB_Coverage) > 1 else '0')
            row.append(str(float(statistics.mean(DSB_Misses)))  if len(DSB_Misses) > 1 else '0')
            row.append(str(float(statistics.mean(IpDSB_Miss_Ret)))  if len(IpDSB_Miss_Ret) > 1 else '0')
            row.append(str(float(statistics.mean(CLKS)))  if len(CLKS) > 1 else '0')
            row.append(str(float(statistics.mean(Execute_per_Issue)))  if len(Execute_per_Issue) > 1 else '0')
            row.append(str(float(statistics.mean(ILP)))  if len(ILP) > 1 else '0')
            row.append(str(float(statistics.mean(Execute)))  if len(Execute) > 1 else '0')
            row.append(str(float(statistics.mean(FP_Arith_Utilization)))  if len(FP_Arith_Utilization) > 1 else '0')
            row.append(str(float(statistics.mean(Core_Bound_Likely)))  if len(Core_Bound_Likely) > 1 else '0')
            row.append(str(float(statistics.mean(GFLOPs)))  if len(GFLOPs) > 1 else '0')
            row.append(str(float(statistics.mean(IpFLOP)))  if len(IpFLOP) > 1 else '0')
            row.append(str(float(statistics.mean(IpArith)))  if len(IpArith) > 1 else '0')
            row.append(str(float(statistics.mean(IpArith_Scalar_SP)))  if len(IpArith_Scalar_SP) > 1 else '0')
            row.append(str(float(statistics.mean(IpArith_Scalar_DP)))  if len(IpArith_Scalar_DP) > 1 else '0')
            row.append(str(float(statistics.mean(IpArith_AVX128)))  if len(IpArith_AVX128) > 1 else '0')
            row.append(str(float(statistics.mean(IpArith_AVX256)))  if len(IpArith_AVX256) > 1 else '0')
            row.append(str(float(statistics.mean(IpArith_AVX512)))  if len(IpArith_AVX512) > 1 else '0')
            row.append(str(float(statistics.mean(CPU_Utilization)))  if len(CPU_Utilization) > 1 else '0')
            row.append(str(float(statistics.mean(CORE_CLKS)))  if len(CORE_CLKS) > 1 else '0')
            row.append(str(float(statistics.mean(SMT_2T_Utilization)))  if len(SMT_2T_Utilization) > 1 else '0')
            row.append(str(float(statistics.mean(IpLoad)))  if len(IpLoad) > 1 else '0')
            row.append(str(float(statistics.mean(IpStore)))  if len(IpStore) > 1 else '0')
            row.append(str(float(statistics.mean(IpSWPF)))  if len(IpSWPF) > 1 else '0')
            row.append(str(float(statistics.mean(DSB_Switch_Cost)))  if len(DSB_Switch_Cost) > 1 else '0')
            row.append(str(float(statistics.mean(Turbo_Utilization)))  if len(Turbo_Utilization) > 1 else '0')
            row.append(str(float(statistics.mean(Power_License0_Utilization)))  if len(Power_License0_Utilization) > 1 else '0')
            row.append(str(float(statistics.mean(Power_License1_Utilization)))  if len(Power_License1_Utilization) > 1 else '0')
            row.append(str(float(statistics.mean(Power_License2_Utilization)))  if len(Power_License2_Utilization) > 1 else '0')
            row.append(str(float(statistics.mean(Kernel_Utilization)))  if len(Kernel_Utilization) > 1 else '0')
            row.append(str(float(statistics.mean(Kernel_CPI)))  if len(Kernel_CPI) > 1 else '0')
            row.append(str(float(statistics.mean(IpFarBranch)))  if len(IpFarBranch) > 1 else '0')
            row.append(str(float(statistics.mean(Time)))  if len(Time) > 1 else '0')
            row.append(str(float(statistics.mean(Socket_CLKS)))  if len(Socket_CLKS) > 1 else '0')

            # Level 1             
            row.append(str(float(statistics.stdev(Frontend_Bound))) if len(Frontend_Bound) > 1 else '0')
            row.append(str(float(statistics.stdev(Bad_Speculation))) if len(Bad_Speculation) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound))) if len(Backend_Bound) > 1 else '0')
            row.append(str(float(statistics.stdev(Retiring))) if len(Retiring) > 1 else '0')
            
            # Level 2
            row.append(str(float(statistics.stdev(Frontend_Bound_Fetch_Bandwidth))) if len(Frontend_Bound_Fetch_Bandwidth) > 1 else '0')
            row.append(str(float(statistics.stdev(Frontend_Bound_Fetch_Latency))) if len(Frontend_Bound_Fetch_Latency) > 1 else '0')
            row.append(str(float(statistics.stdev(Bad_Speculation_Branch_Mispredicts))) if len(Bad_Speculation_Branch_Mispredicts) > 1 else '0')
            row.append(str(float(statistics.stdev(Bad_Speculation_Machine_Clears))) if len(Bad_Speculation_Machine_Clears) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound))) if len(Backend_Bound_Memory_Bound) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound))) if len(Backend_Bound_Core_Bound) > 1 else '0')
            row.append(str(float(statistics.stdev(Retiring_Heavy_Operations))) if len(Retiring_Heavy_Operations) > 1 else '0')
            row.append(str(float(statistics.stdev(Retiring_Light_Operations))) if len(Retiring_Light_Operations) > 1 else '0')
            
            # Level 3
            row.append(str(float(statistics.stdev(Frontend_Bound_Fetch_Bandwidth_MITE))) if len(Frontend_Bound_Fetch_Bandwidth_MITE) > 1 else '0')
            row.append(str(float(statistics.stdev(Frontend_Bound_Fetch_Bandwidth_DSB))) if len(Frontend_Bound_Fetch_Bandwidth_DSB) > 1 else '0')
            row.append(str(float(statistics.stdev(Frontend_Bound_Fetch_Latency_Branch_Resteers))) if len(Frontend_Bound_Fetch_Latency_Branch_Resteers) > 1 else '0')
            row.append(str(float(statistics.stdev(Frontend_Bound_Fetch_Latency_DSB_Switches))) if len(Frontend_Bound_Fetch_Latency_DSB_Switches) > 1 else '0')
            row.append(str(float(statistics.stdev(Frontend_Bound_Fetch_Latency_ICache_Misses))) if len(Frontend_Bound_Fetch_Latency_ICache_Misses) > 1 else '0')
            row.append(str(float(statistics.stdev(Frontend_Bound_Fetch_Latency_ITLB_Misses))) if len(Frontend_Bound_Fetch_Latency_ITLB_Misses) > 1 else '0')
            row.append(str(float(statistics.stdev(Frontend_Bound_Fetch_Latency_LCP))) if len(Frontend_Bound_Fetch_Latency_LCP) > 1 else '0')
            row.append(str(float(statistics.stdev(Frontend_Bound_Fetch_Latency_MS_Switches))) if len(Frontend_Bound_Fetch_Latency_MS_Switches) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_DRAM_Bound))) if len(Backend_Bound_Memory_Bound_DRAM_Bound) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_L1_Bound))) if len(Backend_Bound_Memory_Bound_L1_Bound) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_L2_Bound))) if len(Backend_Bound_Memory_Bound_L2_Bound) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_L3_Bound))) if len(Backend_Bound_Memory_Bound_L3_Bound) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_Store_Bound))) if len(Backend_Bound_Memory_Bound_Store_Bound) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Divider))) if len(Backend_Bound_Core_Bound_Divider) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Ports_Utilization))) if len(Backend_Bound_Core_Bound_Ports_Utilization) > 1 else '0')
            row.append(str(float(statistics.stdev(Retiring_Heavy_Operations_Few_Uops_Instructions))) if len(Retiring_Heavy_Operations_Few_Uops_Instructions) > 1 else '0')
            row.append(str(float(statistics.stdev(Retiring_Heavy_Operations_Microcode_Sequencer))) if len(Retiring_Heavy_Operations_Microcode_Sequencer) > 1 else '0')
            row.append(str(float(statistics.stdev(Retiring_Light_Operations_FP_Arith))) if len(Retiring_Light_Operations_FP_Arith) > 1 else '0')
            row.append(str(float(statistics.stdev(Retiring_Light_Operations_Fused_Instructions))) if len(Retiring_Light_Operations_Fused_Instructions) > 1 else '0')
            row.append(str(float(statistics.stdev(Retiring_Light_Operations_Memory_Operations))) if len(Retiring_Light_Operations_Memory_Operations) > 1 else '0')
            row.append(str(float(statistics.stdev(Retiring_Light_Operations_Non_Fused_Branches))) if len(Retiring_Light_Operations_Non_Fused_Branches) > 1 else '0')
            row.append(str(float(statistics.stdev(Retiring_Light_Operations_Nop_Instructions))) if len(Retiring_Light_Operations_Nop_Instructions) > 1 else '0')
 

            #Level 4
            row.append(str(float(statistics.stdev(Frontend_Bound_Fetch_Latency_Branch_Resteers_Unknown_Branches))) if len(Frontend_Bound_Fetch_Latency_Branch_Resteers_Unknown_Branches) > 1 else '0')
            row.append(str(float(statistics.stdev(Frontend_Bound_Fetch_Latency_Branch_Resteers_Mispredicts_Resteers))) if len(Frontend_Bound_Fetch_Latency_Branch_Resteers_Mispredicts_Resteers) > 1 else '0')
            row.append(str(float(statistics.stdev(Frontend_Bound_Fetch_Latency_Branch_Resteers_Clears_Resteers))) if len(Frontend_Bound_Fetch_Latency_Branch_Resteers_Clears_Resteers) > 1 else '0')
            row.append(str(float(statistics.stdev(Frontend_Bound_Fetch_Bandwidth_MITE_Decoder0_Alone))) if len(Frontend_Bound_Fetch_Bandwidth_MITE_Decoder0_Alone) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load))) if len(Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store))) if len(Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_L1_Bound_Store_Fwd_Blk))) if len(Backend_Bound_Memory_Bound_L1_Bound_Store_Fwd_Blk) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_L1_Bound_Lock_Latency))) if len(Backend_Bound_Memory_Bound_L1_Bound_Lock_Latency) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_L3_Bound_Contested_Accesses))) if len(Backend_Bound_Memory_Bound_L3_Bound_Contested_Accesses) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_L3_Bound_Data_Sharing))) if len(Backend_Bound_Memory_Bound_L3_Bound_Data_Sharing) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_L3_Bound_SQ_Full))) if len(Backend_Bound_Memory_Bound_L3_Bound_SQ_Full) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Bandwidth))) if len(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Bandwidth) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency))) if len(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_Store_Bound_Store_Latency))) if len(Backend_Bound_Memory_Bound_Store_Bound_Store_Latency) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_Store_Bound_False_Sharing))) if len(Backend_Bound_Memory_Bound_Store_Bound_False_Sharing) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_L1_Bound_Split_Loads))) if len(Backend_Bound_Memory_Bound_L1_Bound_Split_Loads) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_L1_Bound_4K_Aliasing))) if len(Backend_Bound_Memory_Bound_L1_Bound_4K_Aliasing) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_L1_Bound_FB_Full))) if len(Backend_Bound_Memory_Bound_L1_Bound_FB_Full) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_L3_Bound_L3_Hit_Latency))) if len(Backend_Bound_Memory_Bound_L3_Bound_L3_Hit_Latency) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_Store_Bound_Split_Stores))) if len(Backend_Bound_Memory_Bound_Store_Bound_Split_Stores) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_1)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_1) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_2)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_2) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m) > 1 else '0')
            row.append(str(float(statistics.stdev(Retiring_Light_Operations_FP_Arith_X87_Use)))  if len(Retiring_Light_Operations_FP_Arith_X87_Use) > 1 else '0')
            row.append(str(float(statistics.stdev(Retiring_Light_Operations_FP_Arith_FP_Scalar)))  if len(Retiring_Light_Operations_FP_Arith_FP_Scalar) > 1 else '0')
            row.append(str(float(statistics.stdev(Retiring_Light_Operations_FP_Arith_FP_Vector)))  if len(Retiring_Light_Operations_FP_Arith_FP_Vector) > 1 else '0')
            row.append(str(float(statistics.stdev(Retiring_Heavy_Operations_Microcode_Sequencer_Assists)))  if len(Retiring_Heavy_Operations_Microcode_Sequencer_Assists) > 1 else '0')
            row.append(str(float(statistics.stdev(Retiring_Heavy_Operations_Microcode_Sequencer_CISC)))  if len(Retiring_Heavy_Operations_Microcode_Sequencer_CISC) > 1 else '0')

            #Level 5
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Hit)))  if len(Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Hit) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Miss)))  if len(Backend_Bound_Memory_Bound_L1_Bound_DTLB_Load_Load_STLB_Miss) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Hit)))  if len(Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Hit) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Miss)))  if len(Backend_Bound_Memory_Bound_Store_Bound_DTLB_Store_Store_STLB_Miss) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_Cache)))  if len(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_Cache) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Local_DRAM)))  if len(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Local_DRAM) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_DRAM)))  if len(Backend_Bound_Memory_Bound_DRAM_Bound_MEM_Latency_Remote_DRAM) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Serializing_Operation))) if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Serializing_Operation) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Mixing_Vectors)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_0_Mixing_Vectors) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization) > 1 else '0')
            row.append(str(float(statistics.stdev(Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_128b))) if len(Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_128b) > 1 else '0')
            row.append(str(float(statistics.stdev(Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_256b))) if len(Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_256b) > 1 else '0')
            row.append(str(float(statistics.stdev(Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_512b)))  if len(Retiring_Light_Operations_FP_Arith_FP_Vector_FP_Vector_512b) > 1 else '0')


            #Level 6
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_0)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_0) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_1)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_1) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_5)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_5) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_6)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_ALU_Op_Utilization_Port_6) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_2)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_2) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_3)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Load_Op_Utilization_Port_3) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_4)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_4) > 1 else '0')
            row.append(str(float(statistics.stdev(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_7)))  if len(Backend_Bound_Core_Bound_Ports_Utilization_Ports_Utilized_3m_Store_Op_Utilization_Port_7) > 1 else '0')


            #metrics

            row.append(str(float(statistics.stdev(SLOTS)))  if len(SLOTS) > 1 else '0')
            row.append(str(float(statistics.stdev(CoreIPC)))  if len(CoreIPC) > 1 else '0')
            row.append(str(float(statistics.stdev(Instructions)))  if len(Instructions) > 1 else '0')
            row.append(str(float(statistics.stdev(IpCall)))  if len(IpCall) > 1 else '0')
            row.append(str(float(statistics.stdev(IpTB)))  if len(IpTB) > 1 else '0')
            row.append(str(float(statistics.stdev(BpTkBranch)))  if len(BpTkBranch) > 1 else '0')
            row.append(str(float(statistics.stdev(Cond_NT)))  if len(Cond_NT) > 1 else '0')
            row.append(str(float(statistics.stdev(Cond_TK)))  if len(Cond_TK) > 1 else '0')
            row.append(str(float(statistics.stdev(Mispredictions)))  if len(Mispredictions) > 1 else '0')
            row.append(str(float(statistics.stdev(IpMispredict)))  if len(IpMispredict) > 1 else '0')
            row.append(str(float(statistics.stdev(Branch_Misprediction_Cost)))  if len(Branch_Misprediction_Cost) > 1 else '0')
            row.append(str(float(statistics.stdev(CallRet)))  if len(CallRet) > 1 else '0')
            row.append(str(float(statistics.stdev(Jump)))  if len(Jump) > 1 else '0')
            row.append(str(float(statistics.stdev(Memory_Bandwidth)))  if len(Memory_Bandwidth) > 1 else '0')
            row.append(str(float(statistics.stdev(Memory_Latency)))  if len(Memory_Latency) > 1 else '0')
            row.append(str(float(statistics.stdev(Memory_Data_TLBs)))  if len(Memory_Data_TLBs) > 1 else '0')
            row.append(str(float(statistics.stdev(CPI)))  if len(CPI) > 1 else '0')
            row.append(str(float(statistics.stdev(Load_Miss_Real_Latency)))  if len(Load_Miss_Real_Latency) > 1 else '0')
            row.append(str(float(statistics.stdev(MLP)))  if len(MLP) > 1 else '0')
            row.append(str(float(statistics.stdev(L1MPKI)))  if len(L1MPKI) > 1 else '0')
            row.append(str(float(statistics.stdev(L1MPKI_Load)))  if len(L1MPKI_Load) > 1 else '0')
            row.append(str(float(statistics.stdev(L2MPKI)))  if len(L2MPKI) > 1 else '0')
            row.append(str(float(statistics.stdev(L2MPKI_All)))  if len(L2MPKI_All) > 1 else '0')
            row.append(str(float(statistics.stdev(L2MPKI_Load)))  if len(L2MPKI_Load) > 1 else '0')
            row.append(str(float(statistics.stdev(L2HPKI_All)))  if len(L2HPKI_All) > 1 else '0')
            row.append(str(float(statistics.stdev(L2HPKI_Load)))  if len(L2HPKI_Load) > 1 else '0')
            row.append(str(float(statistics.stdev(L3MPKI)))  if len(L3MPKI) > 1 else '0')
            row.append(str(float(statistics.stdev(FB_HPKI)))  if len(FB_HPKI) > 1 else '0')
            row.append(str(float(statistics.stdev(Page_Walks_Utilization)))  if len(Page_Walks_Utilization) > 1 else '0')
            row.append(str(float(statistics.stdev(L1D_Cache_Fill_BW)))  if len(L1D_Cache_Fill_BW) > 1 else '0')
            row.append(str(float(statistics.stdev(L2_Cache_Fill_BW)))  if len(L2_Cache_Fill_BW) > 1 else '0')
            row.append(str(float(statistics.stdev(L3_Cache_Fill_BW)))  if len(L3_Cache_Fill_BW) > 1 else '0')
            row.append(str(float(statistics.stdev(L3_Cache_Access_BW)))  if len(L3_Cache_Access_BW) > 1 else '0')
            row.append(str(float(statistics.stdev(L2_Evictions_Silent_PKI)))  if len(L2_Evictions_Silent_PKI) > 1 else '0')
            row.append(str(float(statistics.stdev(L2_Evictions_NonSilent_PKI)))  if len(L2_Evictions_NonSilent_PKI) > 1 else '0')
            row.append(str(float(statistics.stdev(L1D_Cache_Fill_BW_1T)))  if len(L1D_Cache_Fill_BW_1T) > 1 else '0')
            row.append(str(float(statistics.stdev(L2_Cache_Fill_BW_1T)))  if len(L2_Cache_Fill_BW_1T) > 1 else '0')
            row.append(str(float(statistics.stdev(L3_Cache_Fill_BW_1T)))  if len(L3_Cache_Fill_BW_1T) > 1 else '0')
            row.append(str(float(statistics.stdev(L3_Cache_Access_BW_1T)))  if len(L3_Cache_Access_BW_1T) > 1 else '0')
            row.append(str(float(statistics.stdev(DRAM_BW_Use)))  if len(DRAM_BW_Use) > 1 else '0')
            row.append(str(float(statistics.stdev(MEM_Read_Latency)))  if len(MEM_Read_Latency) > 1 else '0')
            row.append(str(float(statistics.stdev(MEM_DRAM_Read_Latency)))  if len(MEM_DRAM_Read_Latency) > 1 else '0')
            row.append(str(float(statistics.stdev(IO_Write_BW)))  if len(IO_Write_BW) > 1 else '0')
            row.append(str(float(statistics.stdev(IO_Read_BW)))  if len(IO_Read_BW) > 1 else '0')
            row.append(str(float(statistics.stdev(Branching_Overhead)))  if len(Branching_Overhead) > 1 else '0')
            row.append(str(float(statistics.stdev(IPC)))  if len(IPC) > 1 else '0')
            row.append(str(float(statistics.stdev(UPI)))  if len(UPI) > 1 else '0')
            row.append(str(float(statistics.stdev(FLOPc)))  if len(FLOPc) > 1 else '0')
            row.append(str(float(statistics.stdev(Retire)))  if len(Retire) > 1 else '0')
            row.append(str(float(statistics.stdev(Big_Code)))  if len(Big_Code) > 1 else '0')
            row.append(str(float(statistics.stdev(Instruction_Fetch_BW)))  if len(Instruction_Fetch_BW) > 1 else '0')
            row.append(str(float(statistics.stdev(UpTB)))  if len(UpTB) > 1 else '0')
            row.append(str(float(statistics.stdev(IpBranch)))  if len(IpBranch) > 1 else '0')
            row.append(str(float(statistics.stdev(Fetch_UpC)))  if len(Fetch_UpC) > 1 else '0')
            row.append(str(float(statistics.stdev(DSB_Coverage)))  if len(DSB_Coverage) > 1 else '0')
            row.append(str(float(statistics.stdev(DSB_Misses)))  if len(DSB_Misses) > 1 else '0')
            row.append(str(float(statistics.stdev(IpDSB_Miss_Ret)))  if len(IpDSB_Miss_Ret) > 1 else '0')
            row.append(str(float(statistics.stdev(CLKS)))  if len(CLKS) > 1 else '0')
            row.append(str(float(statistics.stdev(Execute_per_Issue)))  if len(Execute_per_Issue) > 1 else '0')
            row.append(str(float(statistics.stdev(ILP)))  if len(ILP) > 1 else '0')
            row.append(str(float(statistics.stdev(Execute)))  if len(Execute) > 1 else '0')
            row.append(str(float(statistics.stdev(FP_Arith_Utilization)))  if len(FP_Arith_Utilization) > 1 else '0')
            row.append(str(float(statistics.stdev(Core_Bound_Likely)))  if len(Core_Bound_Likely) > 1 else '0')
            row.append(str(float(statistics.stdev(GFLOPs)))  if len(GFLOPs) > 1 else '0')
            row.append(str(float(statistics.stdev(IpFLOP)))  if len(IpFLOP) > 1 else '0')
            row.append(str(float(statistics.stdev(IpArith)))  if len(IpArith) > 1 else '0')
            row.append(str(float(statistics.stdev(IpArith_Scalar_SP)))  if len(IpArith_Scalar_SP) > 1 else '0')
            row.append(str(float(statistics.stdev(IpArith_Scalar_DP)))  if len(IpArith_Scalar_DP) > 1 else '0')
            row.append(str(float(statistics.stdev(IpArith_AVX128)))  if len(IpArith_AVX128) > 1 else '0')
            row.append(str(float(statistics.stdev(IpArith_AVX256)))  if len(IpArith_AVX256) > 1 else '0')
            row.append(str(float(statistics.stdev(IpArith_AVX512)))  if len(IpArith_AVX512) > 1 else '0')
            row.append(str(float(statistics.stdev(CPU_Utilization)))  if len(CPU_Utilization) > 1 else '0')
            row.append(str(float(statistics.stdev(CORE_CLKS)))  if len(CORE_CLKS) > 1 else '0')
            row.append(str(float(statistics.stdev(SMT_2T_Utilization)))  if len(SMT_2T_Utilization) > 1 else '0')
            row.append(str(float(statistics.stdev(IpLoad)))  if len(IpLoad) > 1 else '0')
            row.append(str(float(statistics.stdev(IpStore)))  if len(IpStore) > 1 else '0')
            row.append(str(float(statistics.stdev(IpSWPF)))  if len(IpSWPF) > 1 else '0')
            row.append(str(float(statistics.stdev(DSB_Switch_Cost)))  if len(DSB_Switch_Cost) > 1 else '0')
            row.append(str(float(statistics.stdev(Turbo_Utilization)))  if len(Turbo_Utilization) > 1 else '0')
            row.append(str(float(statistics.stdev(Power_License0_Utilization)))  if len(Power_License0_Utilization) > 1 else '0')
            row.append(str(float(statistics.stdev(Power_License1_Utilization)))  if len(Power_License1_Utilization) > 1 else '0')
            row.append(str(float(statistics.stdev(Power_License2_Utilization)))  if len(Power_License2_Utilization) > 1 else '0')
            row.append(str(float(statistics.stdev(Kernel_Utilization)))  if len(Kernel_Utilization) > 1 else '0')
            row.append(str(float(statistics.stdev(Kernel_CPI)))  if len(Kernel_CPI) > 1 else '0')
            row.append(str(float(statistics.stdev(IpFarBranch)))  if len(IpFarBranch) > 1 else '0')
            row.append(str(float(statistics.stdev(Time)))  if len(Time) > 1 else '0')
            row.append(str(float(statistics.stdev(Socket_CLKS)))  if len(Socket_CLKS) > 1 else '0')
                        
        raw.append(row)
    return raw

def get_CPI_stack_per_qps (stats,system_confs, qps_list):
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    raw = []
    header_row = []
    header_row.append('QPS')
    for system_conf in system_confs:  
        header_row.append('Frontend_Bound')
               
    raw.append(header_row)
    for i, qps in enumerate(qps_list):
        row = [str(qps)]
        Frontend_Bound = [] 
        for system_conf in system_confs:          
            instance_name = system_conf_fullname(system_conf) + shortname(qps)
            for stat in stats[instance_name]:
                
                row = [str(qps)]            
                system_stats = stat['server']

                Frontend_Bound.extend(sum_perf(system_stats['Frontend_Bound']))
                Frontend_Bound = [i for i in Frontend_Bound if int(i) != 0]
                row.append(str(Frontend_Bound))
                raw.append(row)                

    return raw

    
def get_links_transactions_per_target_qps(stats, system_confs, qps_list):
    
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    raw = []
    header_row = []
    header_row.append('QPS')
    for system_conf in system_confs:
        
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_CRd-avg')
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_DRd-avg')
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_ItoM-avg')
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_PCIRdCur-avg')
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_PRd-avg')
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_RFO-avg')
        
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_WiL-avg')
        
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_CRd-avg')
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_DRd-avg')
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_ItoM-avg')
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_PCIRdCur-avg')
        
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_PRd-avg')
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_RFO-avg')
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_WiL-avg')
        
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_UPI0_In-avg')
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_UPI0_Out-avg')
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_UPI1_In-avg')
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_UPI1_Out-avg')
        
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_UPI0_In-avg')
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_UPI0_Out-avg')
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_UPI1_In-avg')
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_UPI1_Out-avg')
              
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_CRd-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_DRd-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_ItoM-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_PCIRdCur-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_PRd-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_RFO-stdv')
        
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_WiL-stdv')
        
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_CRd-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_DRd-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_ItoM-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_PCIRdCur-stdv')
        
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_PRd-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_RFO-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_WiL-stdv')
        
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_UPI0_In-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_UPI0_Out-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_UPI1_In-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'SKT0_UPI1_Out-stdv')
        
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_UPI0_In-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_UPI0_Out-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_UPI1_In-stdv')
        header_row.append(system_conf_shortname(system_conf) + 'SKT1_UPI1_Out-stdv')
        
    raw.append(header_row)
    for i, qps in enumerate(qps_list):
        row = [str(qps)]
        for system_conf in system_confs:
            
            SKT0_CRd = []
            SKT0_DRd = []
            SKT0_ItoM = []
            SKT0_PCIRdCur = []
            SKT0_PRd = []
            SKT0_RFO = []
        
            SKT0_WiL = []
        
            SKT1_CRd = []
            SKT1_DRd = []
            SKT1_ItoM = []
            SKT1_PCIRdCur = []
        
            SKT1_PRd = []
            SKT1_RFO = []
            SKT1_WiL = []
        
            SKT0_UPI0_In = []
            SKT0_UPI0_Out = []
            SKT0_UPI1_In = []
            SKT0_UPI1_Out = []
        
            SKT1_UPI0_In = []
            SKT1_UPI0_Out = []
            SKT1_UPI1_In = []
            SKT1_UPI1_Out = []
            
            instance_name = system_conf_fullname(system_conf) + shortname(qps)
            for stat in stats[instance_name]:
                system_stats = {}
                system_stats = stat['server']                             
                
                SKT0_CRd.append(avg_pcie(system_stats['SKT0_CRd']))
                SKT0_DRd.append(avg_pcie(system_stats['SKT0_DRd']))
                SKT0_ItoM.append(avg_pcie(system_stats['SKT0_ItoM']))
                SKT0_PCIRdCur.append(avg_pcie(system_stats['SKT0_PCIRdCur']))
                SKT0_PRd.append(avg_pcie(system_stats['SKT0_PRd']))
                SKT0_RFO.append(avg_pcie(system_stats['SKT0_RFO']))
                SKT0_WiL.append(avg_pcie(system_stats['SKT0_WiL']))
                
                SKT1_CRd.append(avg_pcie(system_stats['SKT1_CRd']))
                SKT1_DRd.append(avg_pcie(system_stats['SKT1_DRd']))
                SKT1_ItoM.append(avg_pcie(system_stats['SKT1_ItoM']))
                SKT1_PCIRdCur.append(avg_pcie(system_stats['SKT1_PCIRdCur']))
                SKT1_PRd.append(avg_pcie(system_stats['SKT1_PRd']))
                SKT1_RFO.append(avg_pcie(system_stats['SKT1_RFO']))
                SKT1_WiL.append(avg_pcie(system_stats['SKT1_WiL']))
                
                SKT0_UPI0_In.append(avg_util(system_stats['SKT0_UPI0_In']))
                SKT0_UPI0_Out.append(avg_util(system_stats['SKT0_UPI0_Out']))
                SKT0_UPI1_In.append(avg_util(system_stats['SKT0_UPI1_In']))
                SKT0_UPI1_Out.append(avg_util(system_stats['SKT0_UPI1_Out']))
                
                SKT1_UPI0_In.append(avg_util(system_stats['SKT1_UPI0_In']))
                SKT1_UPI0_Out.append(avg_util(system_stats['SKT1_UPI0_Out']))
                SKT1_UPI1_In.append(avg_util(system_stats['SKT1_UPI1_In']))
                SKT1_UPI1_Out.append(avg_util(system_stats['SKT1_UPI1_Out']))
                     
                   
            row.append(str(statistics.mean(SKT0_CRd)))
            row.append(str(statistics.mean(SKT0_DRd)))
            row.append(str(statistics.mean(SKT0_ItoM)))
            row.append(str(statistics.mean(SKT0_PCIRdCur)))
            row.append(str(statistics.mean(SKT0_PRd)))
            #row.append(str(statistics.mean(dtlb_load_misses_walk_active)))
            row.append(str(statistics.mean(SKT0_RFO)))
            row.append(str(statistics.mean(SKT0_WiL)))
            
            row.append(str(statistics.mean(SKT1_CRd)))
            row.append(str(statistics.mean(SKT1_DRd)))
            row.append(str(statistics.mean(SKT1_ItoM)))
            row.append(str(statistics.mean(SKT1_PCIRdCur)))
            row.append(str(statistics.mean(SKT1_PRd)))
            #row.append(str(statistics.mean(dtlb_load_misses_walk_active)))
            row.append(str(statistics.mean(SKT1_RFO)))
            row.append(str(statistics.mean(SKT1_WiL)))
            
            
            row.append(str(statistics.mean(SKT0_UPI0_In)))
            row.append(str(statistics.mean(SKT0_UPI0_Out)))
            row.append(str(statistics.mean(SKT0_UPI1_In)))
            row.append(str(statistics.mean(SKT0_UPI1_Out)))
                  
            row.append(str(statistics.mean(SKT1_UPI0_In)))
            row.append(str(statistics.mean(SKT1_UPI0_Out)))
            row.append(str(statistics.mean(SKT1_UPI1_In)))
            row.append(str(statistics.mean(SKT1_UPI1_Out)))       
                        
        raw.append(row)
    return raw

def get_server_latency_per_target_qps(stats, system_confs, qps_list):
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    raw = []
    header_row = []
    header_row.append('QPS')
    for system_conf in system_confs:
        header_row.append(system_conf_shortname(system_conf) + 'user-time ') 
        header_row.append(system_conf_shortname(system_conf) + 'kernel-time') 
        header_row.append(system_conf_shortname(system_conf) + 'average-latency') 
        
    raw.append(header_row)
    for i, qps in enumerate(qps_list):
        row = [str(qps)]
        for system_conf in system_confs:
            user_time = []
            kernel_time = []
            
            instance_name = system_conf_fullname(system_conf) + shortname(qps)
            for stat in stats[instance_name]:
                system_stats = stat['server']
                user_time.append((system_stats['rusage_user'][0]))
                kernel_time.append((system_stats['rusage_system'][0]))
                 
            row.append(str(float(statistics.mean(user_time))))
            row.append(str(float(statistics.mean(kernel_time))))
            
            #time fixed to 120000000 fix to dynamic
            avg_latency_per_qps = (float(statistics.mean(user_time)) + float(statistics.mean(kernel_time)))/(qps*120)*1000000
            row.append(str(avg_latency_per_qps))
            
        raw.append(row)
    return raw


def plot_power_per_target_qps(stats, system_confs, qps_list, filter=None):
    raw = get_power_per_target_qps(stats, system_confs, qps_list)
    return plot_X_per_target_qps(raw, qps_list, 'Request Rate (KQPS)', 'Power (W)', filter)

def write_csv(filename, rows):
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',',
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
        for row in rows:
            writer.writerow(row)    

def write_csv_all(stats, system_confs, qps_list):
    for system_conf in system_confs:
        #raw = get_residency_per_target_qps_seconds(stats, system_conf, qps_list)
        #write_csv(system_conf_fullname(system_conf) + 'residency_per_target_qps_seconds' + '.csv', raw)
        #raw = get_residency_per_target_qps(stats, system_conf, qps_list)
        #write_csv(system_conf_fullname(system_conf) + 'residency_per_target_qps' + '.csv', raw)
        #raw = get_usage_per_target_qps(stats, system_conf, qps_list)
        #write_csv(system_conf_fullname(system_conf) + 'usage_per_target_qps' + '.csv', raw)
        #raw = get_total_qps_per_target_qps(stats, system_conf, qps_list)
        #write_csv(system_conf_fullname(system_conf) + 'total_qps_per_target_qps' + '.csv', raw)
        #raw = get_latency_per_target_qps(stats, system_conf, qps_list)
        #write_csv(system_conf_fullname(system_conf) + 'latency_per_target_qps' + '.csv', raw)
        #raw = get_power_per_target_qps(stats, system_conf, qps_list)
        #write_csv(system_conf_fullname(system_conf) + 'power_per_target_qps' + '.csv', raw)
        #raw = get_util_per_target_qps(stats, system_conf, qps_list)
        #write_csv(system_conf_fullname(system_conf) + 'cpu_util_per_target_qps' + '.csv', raw)
        #raw = get_rapl_power_per_target_qps(stats, system_conf, qps_list)
        #write_csv(system_conf_fullname(system_conf) + 'rapl_power_per_target_qps' + '.csv', raw)
        
        #raw = get_links_transactions_per_target_qps(stats, system_conf, qps_list)
        #write_csv(system_conf_fullname(system_conf) + 'links_transacions_per_second_per_target_qps' + '.csv', raw)
        
        raw = get_CPI_stack_qps(stats, system_conf, qps_list)
        write_csv(system_conf_fullname(system_conf) + 'CPI_stack_per_target_qps' + '.csv', raw)
        
        #raw = get_perf_count_per_target_qps(stats, system_conf, qps_list)
        #write_csv(system_conf_fullname(system_conf) + 'perf_count_per_target_qps' + '.csv', raw)
        #raw = get_server_latency_per_target_qps(stats, system_conf, qps_list)
        #write_csv(system_conf_fullname(system_conf) + 'server_latency_per_target_qps' + '.csv', raw)
        
        #raw = get_CPI_stack_per_qps(stats, system_conf, qps_list)
        #write_csv(system_conf_fullname(system_conf) + 'CPI_stack' + '.csv', raw)
        
def filter_system_confs(system_confs, turbo):
    turbo_system_confs = []
    for s in system_confs:
        if s['turbo'] == turbo:
            turbo_system_confs.append(s)
    return turbo_system_confs

def write_latency_to_single_csv(stats, system_confs, qps_list):
    turbo_system_confs = filter_system_confs(system_confs, turbo=True)
    turbo_raw = get_latency_per_target_qps(stats, turbo_system_confs, qps_list)
    noturbo_system_confs = filter_system_confs(system_confs, turbo=False)
    noturbo_raw = get_latency_per_target_qps(stats, noturbo_system_confs, qps_list)
    write_csv('all_latency_per_target_qps' + '.csv', turbo_raw + noturbo_raw)

def write_power_to_single_csv(stats, system_confs, qps_list):
    turbo_system_confs = filter_system_confs(system_confs, turbo=True)
    turbo_raw = get_power_per_target_qps(stats, turbo_system_confs, qps_list)
    noturbo_system_confs = filter_system_confs(system_confs, turbo=False)
    noturbo_raw = get_power_per_target_qps(stats, noturbo_system_confs, qps_list)
    write_csv('all_power_per_target_qps' + '.csv', turbo_raw + [] + noturbo_raw)

def write_total_qps_to_single_csv(stats, system_confs, qps_list):
    turbo_system_confs = filter_system_confs(system_confs, turbo=True)
    turbo_raw = get_total_qps_per_target_qps(stats, turbo_system_confs, qps_list)
    noturbo_system_confs = filter_system_confs(system_confs, turbo=False)
    noturbo_raw = get_total_qps_per_target_qps(stats, noturbo_system_confs, qps_list)
    write_csv('all_total_qps_per_target_qps' + '.csv', turbo_raw + noturbo_raw)

def plot(stats, system_confs, qps_list, interactive):
    pdf = matplotlib.backends.backend_pdf.PdfPages("output.pdf")
    for system_conf in system_confs:
        firstPage = plt.figure()
        firstPage.clf()
        txt = system_conf_fullname(system_conf)
        firstPage.text(0.5,0.5, txt, transform=firstPage.transFigure, size=14, ha="center")
        pdf.savefig(firstPage)
        plt.close()
        if system_conf['kernelconfig'] != 'disable_cstates':
            fig1 = plot_residency_per_target_qps(stats, system_conf, qps_list)
            pdf.savefig(fig1)
        fig2 = plot_total_qps_per_target_qps(stats, system_conf, qps_list)
        pdf.savefig(fig2)
        fig3 = plot_latency_per_target_qps(stats, system_conf, qps_list)
        pdf.savefig(fig3)
        fig4 = plot_power_per_target_qps(stats, system_conf, qps_list)
        pdf.savefig(fig4)
        if interactive:
            plt.show()
        plt.close(fig1)
        plt.close(fig2)
        plt.close(fig3)
        # plt.close(fig4)
    pdf.close()

def plot_stack(stats, system_confs, qps_list, interactive=True):
    pdf = matplotlib.backends.backend_pdf.PdfPages("all.pdf")
    for system_conf in system_confs:
        if system_conf['kernelconfig'] != 'disable_cstates':
            fig1 = plot_residency_per_target_qps(stats, system_conf, qps_list)
            pdf.savefig(fig1)
    fig2 = plot_total_qps_per_target_qps(stats, system_confs, qps_list)
    pdf.savefig(fig2)
    fig3 = plot_latency_per_target_qps(stats, system_confs, qps_list, filter = ['read_avg'])
    pdf.savefig(fig3)
    fig4 = plot_power_per_target_qps(stats, system_confs, qps_list)
    pdf.savefig(fig4)
    if interactive:
        plt.show()
    plt.close(fig2)
    plt.close(fig3)
    # plt.close(fig4)
    pdf.close()

def main(argv):
    stats_root_dir = argv[1]
    stats = parse_multiple_instances_stats(stats_root_dir)
    all_system_confs = [
        {'turbo': False, 'kernelconfig': 'baseline', },
        {'turbo': False, 'kernelconfig': 'disable_cstates', },
        {'turbo': False, 'kernelconfig': 'disable_c6'},
        {'turbo': False, 'kernelconfig': 'disable_c1e_c6'},
        {'turbo': False, 'kernelconfig': 'quick_c1'},
        {'turbo': False, 'kernelconfig': 'quick_c1_disable_c6'},
        {'turbo': False, 'kernelconfig': 'quick_c1_c1e'},
        {'turbo': True, 'kernelconfig': 'baseline'},
        {'turbo': True, 'kernelconfig': 'disable_cstates'},
        {'turbo': True, 'kernelconfig': 'disable_c6'},
        {'turbo': True, 'kernelconfig': 'disable_c1e_c6'},
        {'turbo': True, 'kernelconfig': 'quick_c1'},
        {'turbo': True, 'kernelconfig': 'quick_c1_disable_c6'},
        {'turbo': True, 'kernelconfig': 'quick_c1_c1e'},
    ]

    core_freq_varying_system_confs = [
        {'turbo': False, 'kernelconfig': 'baseline', 'freq': 1400},
        {'turbo': False, 'kernelconfig': 'baseline', 'freq': 1600},
        {'turbo': False, 'kernelconfig': 'baseline', 'freq': 1800},
        {'turbo': False, 'kernelconfig': 'baseline', 'freq': 2000},
        {'turbo': False, 'kernelconfig': 'baseline', 'freq': 2200},
        {'turbo': False, 'kernelconfig': 'baseline', 'freq': 2400},
        {'turbo': False, 'kernelconfig': 'disable_cstates', 'freq': 1400},
        {'turbo': False, 'kernelconfig': 'disable_cstates', 'freq': 1600},
        {'turbo': False, 'kernelconfig': 'disable_cstates', 'freq': 1800},
        {'turbo': False, 'kernelconfig': 'disable_cstates', 'freq': 2000},
        {'turbo': False, 'kernelconfig': 'disable_cstates', 'freq': 2200},
        {'turbo': False, 'kernelconfig': 'disable_cstates', 'freq': 2400},
    ]

    uncore_dynamic_system_confs = [
       {'turbo': False, 'kernelconfig': 'disable_c1e_c6'},
       {'turbo': True, 'kernelconfig': 'baseline'},
       {'turbo': True, 'kernelconfig': 'disable_c6'},
       {'turbo': True, 'kernelconfig': 'disable_c1e_c6'},
       {'turbo': True, 'kernelconfig': 'disable_cstates'},
    ]

    uncore_fixed_system_confs = [
       #{'turbo': True, 'kernelconfig': 'baseline', 'ht': False},
        #{'turbo': False, 'kernelconfig': 'disable_c6'},
       #{'turbo': False, 'kernelconfig': 'disable_c6', 'ht': False},
       #{'turbo': False, 'kernelconfig': 'disable_cstates', 'ht': False},
       {'turbo': False, 'kernelconfig': 'baseline', 'ht': False},
       #{'turbo': False, 'kernelconfig': 'disable_c6', 'ht': False},
       {'turbo': False, 'kernelconfig': 'disable_cstates', 'ht': False},
       {'turbo': False, 'kernelconfig': 'disable_c1e_c6', 'ht': False},
       #{'turbo': False, 'kernelconfig': 'disable_c1e_c6', 'ht': False},
       #{'turbo': False, 'kernelconfig': 'disable_c1e_c6', 'ht': False},
       #{'turbo': True, 'kernelconfig': 'baseline', 'ht': False, 'idlegovernor' : '', 'tickless' : ''},
       #{'turbo': True, 'kernelconfig': 'disable_c1e_c6', 'ht': True},
       #{'turbo': True, 'kernelconfig': 'disable_c1e_c6', 'ht': False},
       #{'turbo': False, 'kernelconfig': 'disable_cstates'},
    ]

    #system_confs = core_freq_varying_system_confs
    system_confs = uncore_fixed_system_confs
    #system_confs = uncore_dynamic_system_confs

    #qps_list = [10000, 50000, 100000, 200000, 300000, 400000, 500000, 600000, 700000, 800000]
    #qps_list = [10000, 50000, 100000, 200000, 300000, 400000, 500000]
    qps_list = [1500]
    #plot(stats, system_confs, qps_list, interactive=False)
    #plot_stack(stats, system_confs, qps_list, interactive=True)
    write_csv_all(stats, system_confs, qps_list)
    #write_latency_to_single_csv(stats, system_confs, qps_list)
    #write_power_to_single_csv(stats, system_confs, qps_list)
    #write_total_qps_to_single_csv(stats, system_confs, qps_list)

if __name__ == '__main__':
    main(sys.argv)
