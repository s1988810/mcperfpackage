from xmlrpc.server import SimpleXMLRPCServer
import xmlrpc.client
import argparse
import functools
import logging
import os
import sys
import socket
import time
import threading
import subprocess 
from subprocess import call
import re
import math

# TODO: ProfilerGroup has a tick thread that wakes up at the minimum sampling period and wakes up each profiler if it has to wake up
# TODO: Use sampling period and sampling length
# def power_state_diff(new_vector, old_vector):
#     diff = []
#     for (new, old) in zip(new_vector, old_vector):
#         diff.append([x[0] - x[1] for x in zip(new, old)])
#     return diff
 
class EventProfiling:
    def __init__(self, sampling_period = 0, sampling_length = 1):
        self.terminate_thread = threading.Condition()
        self.is_active = False
        self.sampling_period = sampling_period
        self.sampling_length = sampling_length

    def profile_thread(self):
        logging.info("Profiling thread started")
        self.terminate_thread.acquire()
        while self.is_active:
            timestamp = str(int(time.time()))
            self.terminate_thread.release()
            self.sample(timestamp)
            self.terminate_thread.acquire()
            if self.is_active:
                self.terminate_thread.wait(timeout=self.sampling_period - self.sampling_length)
        self.terminate_thread.release()
        timestamp = str(int(time.time()))
        self.zerosample(timestamp)
        logging.info("Profiling thread terminated")

    def start(self):
        
        self.clear()
        if self.sampling_period:
            
            self.is_active=True
            self.thread = threading.Thread(target=EventProfiling.profile_thread, args=(self,))
            self.thread.daemon = True
            self.thread.start()
        else:
            
            timestamp = str(int(time.time()))
            self.sample(timestamp)

    def stop(self):
        if self.sampling_period:
            self.terminate_thread.acquire()
            self.interrupt_sample()
            self.is_active=False
            self.terminate_thread.notify()
            self.terminate_thread.release()
        else:
            timestamp = str(int(time.time()))
            self.sample(timestamp)

class TopDownProfiling(EventProfiling):
    def __init__(self, sampling_period=30,sampling_length=30, iteration=1):
        
        super().__init__(sampling_period, sampling_length)
        self.pmu_path = self.find_pmu_path()
        logging.info('Pmu found at {}'.format(self.pmu_path)) 
        
        self.events = self.get_events()      
        self.timeseries = {}
        self.iteration=iteration
	
        for e in self.events:
            self.timeseries[e] = []
         
        
        #get pid of memcached    
        cmd = ['pgrep', 'memcached']
        result = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        out = result.stdout.decode('utf-8').splitlines() + result.stderr.decode('utf-8').splitlines()
        self.pid=out[0]
    
    def find_pmu_path(self):
        cmd = ['find', '/users/ganton12', '-name', 'toplev.py']
        result = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        out = result.stdout.decode('utf-8').splitlines() + result.stderr.decode('utf-8').splitlines()
        return out[0]
    
    def get_events(self):
        events = []
        cmd = ['sudo', 'python3', self.pmu_path, '-l6', '-v', '-m', '--no-desc', '/users/ganton12/mcperf/spin', '1']
        result = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        out = result.stdout.decode('utf-8').splitlines() + result.stderr.decode('utf-8').splitlines()
         
        
        for l in out:
            l = l.lstrip()
            m = re.match("[A-Z]+([a-zA-Z0-9\/\._])+\s+([a-zA-Z0-9\._]+)\s+", l) 
            if m:
                events.append(m.group(2))
        
        return events

    def sample(self, timestamp):
    
        level=self.iteration%6 + 1
        
        cmd = ['sudo', self.pmu_path, '-l' + str(level), '-v', '-m', '--no-desc', '-I', '30000', '-p', self.pid]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        out = result.stdout.decode('utf-8').splitlines() + result.stderr.decode('utf-8').splitlines()
              
        for l in out:
            print(l)
            l = l.strip()
            m = re.match("([0-9]+\.+[0-9]+)\s([A-Z]+[a-zA-Z\/]*)+\s+([a-zA-z0-9\._]+)\s+(%)+\s[a-zA-Z]+\s+([0-9]+\.+[0-9]+)\s",l) 
            if m:
                print(m.group(3) + " " + m.group(5))
                self.timeseries[m.group(3)].append((timestamp, str(m.group(5))))
          
        
    def zerosample(self, timestamp):
        for e in self.events:
            self.timeseries[e].append((timestamp, str(0.0)))

    def interrupt_sample(self):
        os.system("sudo pkill -9 perf")

    def clear(self):
        self.timeseries = {}
        for e in self.events:
            self.timeseries[e] = []

    def report(self):
        return self.timeseries

class VtunePcieProfiling(EventProfiling):
    def __init__(self, sampling_period=1, sampling_length=1):
        super().__init__(sampling_period, sampling_length)
        self.vtune_pcie_path = "/opt/intel/oneapi/vtune/2022.3.0/bin64/vtune"
        
        self.events_label = VtunePcieProfiling.get_events_label()
        self.events = VtunePcieProfiling.get_pcie_events()
        self.timeseries = {}
        for e in self.events:
            self.timeseries.setdefault(e, [])

    def get_events_label():
        events = []
        events.append("Inbound PCIe Read, MB/sec: ")
        events.append("Average Latency, ns: ")
        events.append("Inbound PCIe Write, MB/sec: ")
        events.append("Average Latency, ns: ")
        events.append("Outbound PCIe Read, MB/sec: ")
        events.append("Outbound PCIe Write, MB/sec: ")
        return events 

    def get_pcie_events():
        events = []
        events.append("Inbound_PCIe_Read_BW")
        events.append("Inbound_PCIe_Read_Latency")
        events.append("Inbound_PCIe_Write_BW")
        events.append("Inbound_PCIe_Write_Latency")
        events.append("Outbound_PCIe_Read_BW")
        events.append("Outbound_PCIe_Write_BW")
        return events

    def sample(self, timestamp):
       
        cmd = ['sudo', self.vtune_pcie_path,  '-collect' , 'io' , '--' ,'sleep', '10']
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE)
        out = result.stdout.decode('utf-8').splitlines()
        #print(out)       
        latency_occurences=0
        for l in out:
            print(l)
            for e in self.events_label:
                if e in l:
                  i = self.events_label.index(e)
                  print(l)
                  print(e)
                  print(str(i) + " " + str(latency_occurences))
                  if "Average Latency" in l:
                      self.timeseries[self.events[latency_occurences]].append(l.split(e)[1])
                  else:
                      self.timeseries[self.events[i]].append(l.split(e)[1])
                  latency_occurences = latency_occurences + 1 
        
        print(self.timeseries)
#        for e in self.perf_stats_events:
#            for l in out:
#                l = l.lstrip()
#                if e in l:
#                    value=l.split()[-(len(e.split())+1)]
#                    self.timeseries[e].append((timestamp, str(float(value.replace(',', '')))))
                
    # FIXME: Currently, we add a dummy zero sample when we finish sampling. 
    # This helps us to determine the sampling duration later when we analyze the stats
    # It would be nice to have a more clear solution
    def zerosample(self, timestamp):
        for e in self.events:
            self.timeseries[e].append((timestamp, str(0)))
            
    def interrupt_sample(self):
        pass
        #os.system('sudo /opt/intel/oneapi/vtune/2022.3.0/bin64/vtune -r /users/ganton12/mcperf/r000io -command stop')
        #os.system('sudo pkill -9 vtune')

    def clear(self):
        os.system('sudo rm -r ./r00*')
        self.timeseries = {}
        for e in self.events:
            self.timeseries[e] = []

    def report(self):
        return self.timeseries




class PcmUpiProfiling(EventProfiling):
    def __init__(self, sampling_period=1, sampling_length=1):
        super().__init__(sampling_period, sampling_length)
        self.pcm_upi_path = "/users/ganton12/pcm/build/bin/pcm"
        
        self.events = PcmUpiProfiling.get_upi_events()
        self.timeseries = {}
        for e in self.events:
            cpu_str = "SKT0_{}".format(e)
            self.timeseries.setdefault(cpu_str, [])
            cpu_str = "SKT1_{}".format(e)
            self.timeseries.setdefault(cpu_str, [])

    def get_upi_events():
        events = []
        events.append("UPI0_In")
        events.append("UPI1_In")
        events.append("UPI0_Out")
        events.append("UPI1_Out")
        return events

    def sample(self, timestamp):
       
        cmd = ['sudo', self.pcm_upi_path,  str(self.sampling_length), "-i=1"]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        out = result.stdout.decode('utf-8').splitlines() + result.stderr.decode('utf-8').splitlines()
        socket = {}
        events_out = []
        flag=0

        #for e in self.events:
        #   all_events = all_events + "\t|\t" + e
        #print(all_events) 
        for l in out:
            if "data traffic coming to CPU/socket through UPI" in l:
                events_out = l.split()
                flag=1
                continue
            if flag != 0:
                flag = flag + 1
            if flag >= 5 and flag < 7:
               socket[flag-5] = l.split()
            elif flag >= 7 :
               break
        
        if socket:
            if socket[0][3] == "K":
                self.timeseries["SKT0_UPI0_In"].append((timestamp, str(socket[0][2] + "000")))
                next_index = 4
            elif socket[0][3] == "M":
                self.timeseries["SKT0_UPI0_In"].append((timestamp, str(socket[0][2] + "000000")))
                next_index = 4
            elif socket[0][3] == "G":
                self.timeseries["SKT0_UPI0_In"].append((timestamp, str(socket[0][2] + "000000000")))
                next_index = 4
            else:
                next_index = 3
                self.timeseries["SKT0_UPI0_In"].append((timestamp, str(socket[0][2])))
       
            if len(socket[0]) >= (next_index+1) and socket[0][next_index+1] == "K":
                self.timeseries["SKT0_UPI1_In"].append((timestamp, str(socket[0][next_index] + "000")))
            elif len(socket[0]) >= (next_index+1) and socket[0][next_index+1] == "M":
                self.timeseries["SKT0_UPI1_In"].append((timestamp, str(socket[0][next_index] + "000000")))
            elif len(socket[0]) >= (next_index+1) and socket[0][next_index+1] == "G":
                self.timeseries["SKT0_UPI1_In"].append((timestamp, str(socket[0][next_index] + "000000000")))
            else:
                self.timeseries["SKT0_UPI1_In"].append((timestamp, str(socket[0][next_index-1])))

            if socket[1][3] == "K":
                self.timeseries["SKT1_UPI0_In"].append((timestamp, str(socket[1][2] + "000")))
                next_index = 4
            elif socket[1][3] == "M":
                self.timeseries["SKT1_UPI0_In"].append((timestamp, str(socket[1][2] + "000000")))
            elif len(socket[0]) >= (next_index+1) and socket[0][next_index+1] == "G":
                self.timeseries["SKT1_UPI0_In"].append((timestamp, str(socket[0][next_index] + "000000000")))
                next_index = 4
            else:
                next_index = 3
                self.timeseries["SKT1_UPI0_In"].append((timestamp, str(socket[1][2])))
       
            if len(socket[1]) >= (next_index+1) and socket[1][next_index+1] == "K":
                self.timeseries["SKT1_UPI1_In"].append((timestamp, str(socket[1][next_index] + "000")))
            elif len(socket[1]) >= (next_index+1) and socket[1][next_index+1] == "M":
                self.timeseries["SKT1_UPI1_In"].append((timestamp, str(socket[1][next_index] + "000000")))
            elif len(socket[1]) >= (next_index+1) and socket[1][next_index+1] == "G":
                self.timeseries["SKT1_UPI1_In"].append((timestamp, str(socket[1][next_index] + "000000000")))
            else:
                self.timeseries["SKT1_UPI1_In"].append((timestamp, str(socket[1][next_index-1])))
      
        socket = {}
        flag=0
        for l in out:
            if "data and non-data traffic outgoing from CPU/socket through UPI links" in l:
                events_out = l.split()
                flag=1
                continue
            if flag != 0:
                flag = flag + 1
            if flag >= 5 and flag < 7:
                socket[flag-5] = l.split()
            elif flag > 7:
                break
        
        if socket:
            if socket[0][3] == "K":
                self.timeseries["SKT0_UPI0_Out"].append((timestamp, str(socket[0][2] + "000")))
                next_index = 4
            elif socket[0][3] == "M":
                self.timeseries["SKT0_UPI0_Out"].append((timestamp, str(socket[0][2] + "000000")))
                next_index = 4
            elif socket[0][3] == "G":
                self.timeseries["SKT0_UPI0_Out"].append((timestamp, str(socket[0][2] + "000000000")))
                next_index = 4
            else:
                next_index = 3
                self.timeseries["SKT0_UPI0_Out"].append((timestamp, str(socket[0][2])))
       
            if len(socket[0]) >= (next_index+1) and socket[0][next_index+1] == "K":
                self.timeseries["SKT0_UPI1_Out"].append((timestamp, str(socket[0][next_index] + "000")))
            elif len(socket[0]) >= (next_index+1) and socket[0][next_index+1] == "M":
                self.timeseries["SKT0_UPI1_Out"].append((timestamp, str(socket[0][next_index] + "000000")))
            elif len(socket[0]) >= (next_index+1) and socket[0][next_index+1] == "G":
                self.timeseries["SKT0_UPI1_Out"].append((timestamp, str(socket[0][next_index] + "000000000")))
            else:
                self.timeseries["SKT0_UPI1_Out"].append((timestamp, str(socket[0][next_index-1])))

            if socket[1][3] == "K":
                self.timeseries["SKT1_UPI0_Out"].append((timestamp, str(socket[1][2] + "000")))
                next_index = 4
            elif socket[1][3] == "M":
                self.timeseries["SKT1_UPI0_Out"].append((timestamp, str(socket[1][2] + "000000")))
                next_index = 4
            elif socket[1][3] == "G":
                self.timeseries["SKT1_UPI0_Out"].append((timestamp, str(socket[1][2] + "000000000")))
                next_index = 4
            else:
                next_index = 3
                self.timeseries["SKT1_UPI0_Out"].append((timestamp, str(socket[1][2])))
       
            if len(socket[1]) >= (next_index+1) and socket[1][next_index+1] == "K":
                self.timeseries["SKT1_UPI1_Out"].append((timestamp, str(socket[1][next_index] + "000")))
            elif len(socket[1]) >= (next_index+1) and socket[1][next_index+1] == "M":
                self.timeseries["SKT1_UPI1_Out"].append((timestamp, str(socket[1][next_index] + "000000")))
            elif len(socket[1]) >= (next_index+1) and socket[1][next_index+1] == "G":
                self.timeseries["SKT1_UPI1_Out"].append((timestamp, str(socket[1][next_index] + "000000000")))
            else:
                self.timeseries["SKT1_UPI1_Out"].append((timestamp, str(socket[1][next_index-1])))
       
        
      

#        for e in self.perf_stats_events:
#            for l in out:
#                l = l.lstrip()
#                if e in l:
#                    value=l.split()[-(len(e.split())+1)]
#                    self.timeseries[e].append((timestamp, str(float(value.replace(',', '')))))
                
    # FIXME: Currently, we add a dummy zero sample when we finish sampling. 
    # This helps us to determine the sampling duration later when we analyze the stats
    # It would be nice to have a more clear solution
    def zerosample(self, timestamp):
        for e in self.events:
            cpu_str = "SKT0_{}".format(e)
            self.timeseries[cpu_str].append((timestamp, str(0.0)))
            cpu_str = "SKT1_{}".format(e)
            self.timeseries[cpu_str].append((timestamp, str(0.0)))

    def interrupt_sample(self):
        os.system('sudo pkill -9 pcm')

    def clear(self):
        self.timeseries = {}
        for e in self.events:
            cpu_str = "SKT0_{}".format(e)
            self.timeseries[cpu_str] = []
            cpu_str = "SKT1_{}".format(e)
            self.timeseries[cpu_str] = []

    def report(self):
        return self.timeseries

class PcmPcieProfiling(EventProfiling):
    def __init__(self, sampling_period=1, sampling_length=1):
        super().__init__(sampling_period, sampling_length)
        self.pcm_pcie_path = "/users/ganton12/pcm/build/bin/pcm-pcie"
        
        self.events = PcmPcieProfiling.get_pcie_events()
        self.timeseries = {}
        for e in self.events:
            cpu_str = "SKT0_{}".format(e)
            self.timeseries.setdefault(cpu_str, [])
            cpu_str = "SKT1_{}".format(e)
            self.timeseries.setdefault(cpu_str, [])

    def get_pcie_events():
        events = []
        events.append("PCIRdCur")
        events.append("RFO")
        events.append("CRd")
        events.append("DRd")
        events.append("ItoM")
        events.append("PRd")
        events.append("WiL")  
        return events

    def sample(self, timestamp):
       
        cmd = ['sudo', self.pcm_pcie_path,  str(self.sampling_length/2), "-i=1"]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        out = result.stdout.decode('utf-8').splitlines() + result.stderr.decode('utf-8').splitlines()
        socket = {}
        events_out = []
        flag=0
        all_events = ""
        
        #for e in self.events:
        #   all_events = all_events + "\t|\t" + e
        #print(all_events) 
        for l in out:
            if "Skt " in l:
                events_out = l.split()
                flag=1
                continue
            if flag > 0 and flag < 3 :
                socket[flag-1] = l.split()
                flag = flag + 1
            elif flag > 2:
                break
        
        try:
            while True:
               events_out.remove("|")
        except ValueError:
               pass
        for e in events_out[1:]:
            index_temp = events_out.index(e)
            temp = index_temp
            cur_index=1
            for elem in socket[0][1:]:
                
                if "K" in elem or "M" in elem or "G" in elem:
                    
                    temp = temp + 1
                if cur_index == temp:
                    break
                cur_index = cur_index + 1
            if len(socket[0]) > (cur_index+1) and (socket[0][cur_index+1] != "K" and socket[0][cur_index+1] != "M" and socket[0][cur_index +1] != "G"):
                self.timeseries["SKT0_" + e].append((timestamp, str(socket[0][cur_index])))
            elif len(socket[0]) == (cur_index+1):
                self.timeseries["SKT0_" + e].append((timestamp, str(socket[0][cur_index])))
            elif socket[0][cur_index+1] == "K": 
                self.timeseries["SKT0_" + e].append((timestamp, str(socket[0][cur_index] + "000")))
            elif socket[0][cur_index+1] == "M": 
                self.timeseries["SKT0_" + e].append((timestamp, str(socket[0][cur_index] + "000000")))
            elif socket[0][cur_index+1] == "G": 
                self.timeseries["SKT0_" + e].append((timestamp, str(socket[0][cur_index] + "000000000")))
            
            temp = index_temp
            cur_index=1
            for elem in socket[1][1:]:
                if "K" in elem or "M" in elem or "G" in elem:
                    temp = temp + 1
                if cur_index == temp:
                    break
                cur_index = cur_index + 1
            if len(socket[1]) > (cur_index+1) and socket[1][cur_index+1] != "K" and socket[1][cur_index+1] != "M" and socket[1][cur_index+1] != "G":
                self.timeseries["SKT1_" + e].append((timestamp, str(socket[1][cur_index])))
            elif len(socket[1]) == (cur_index+1):
                self.timeseries["SKT1_" + e].append((timestamp, str(socket[1][cur_index])))
            elif socket[1][cur_index+1] == "K": 
                self.timeseries["SKT1_" + e].append((timestamp, str(socket[1][cur_index] + "000")))
            elif socket[1][cur_index+1] == "M": 
                self.timeseries["SKT1_" + e].append((timestamp, str(socket[1][cur_index] + "000000")))
            elif socket[1][cur_index+1] == "G": 
                self.timeseries["SKT1_" + e].append((timestamp, str(socket[1][cur_index] + "000000000")))
         

#        for e in self.perf_stats_events:
#            for l in out:
#                l = l.lstrip()
#                if e in l:
#                    value=l.split()[-(len(e.split())+1)]
#                    self.timeseries[e].append((timestamp, str(float(value.replace(',', '')))))
                
    # FIXME: Currently, we add a dummy zero sample when we finish sampling. 
    # This helps us to determine the sampling duration later when we analyze the stats
    # It would be nice to have a more clear solution
    def zerosample(self, timestamp):
        for e in self.events:
            cpu_str = "SKT0_{}".format(e)
            self.timeseries[cpu_str].append((timestamp, str(0.0)))
            cpu_str = "SKT1_{}".format(e)
            self.timeseries[cpu_str].append((timestamp, str(0.0)))

    def interrupt_sample(self):
        os.system('sudo pkill -9 pcm-pcie')

    def clear(self):
        self.timeseries = {}
        for e in self.events:
            cpu_str = "SKT0_{}".format(e)
            self.timeseries[cpu_str] = []
            cpu_str = "SKT1_{}".format(e)
            self.timeseries[cpu_str] = []

    def report(self):
        return self.timeseries

class PerfEventProfiling(EventProfiling):
    def __init__(self, sampling_period=1, sampling_length=1, iteration=1):
        print(sampling_period)
        super().__init__(sampling_period, sampling_length)
        self.perf_path = self.find_perf_path()
        
        logging.info('Perf found at {}'.format(self.perf_path)) 
        
        self.events = PerfEventProfiling.get_microarchitectural_events()
        self.perf_stats_events = PerfEventProfiling.get_perf_stat_events()
        
        self.timeseries = {}
        self.iteration=iteration
	
        for e in self.events:
            self.timeseries[e] = []

        #for e in self.perf_stats_events:
         #   self.timeseries[e] = []
        
        print("IRTHAAAAAA")
        #get pid of memcached    
        cmd = ['pgrep', 'memcached']
        result = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        out = result.stdout.decode('utf-8').splitlines() + result.stderr.decode('utf-8').splitlines()
        self.pid=out[0]

    def find_perf_path(self):
        kernel_uname = os.popen('uname -a').read().strip()
        if '4.15.0-159-generic' in kernel_uname:
            return '/usr/bin/perf'
        else:
            return '/mydata/linux-4.15.18/perf'

    def get_perf_power_events(self):
        events = []
        result = subprocess.run([self.perf_path, 'list'], stdout=subprocess.PIPE)
        for l in result.stdout.decode('utf-8').splitlines():
            l = l.lstrip()
            m = re.match("(power/energy-.*/)\s*\[Kernel PMU event]", l)
            if m:
                events.append(m.group(1))

    @staticmethod
    def get_microarchitectural_events():
        events = []
        #events.append("inst_retired.any")
        #events.append("br_inst_retired.all_branches")
        #events.append("br_misp_retired.all_branches")
        #events.append("dtlb_load_misses.miss_causes_a_walk")
        #events.append("dtlb_load_misses.stlb_hit")
        #events.append("dtlb_load_misses.walk_active")
        #events.append("itlb_misses.miss_causes_a_walk")
        #events.append("itlb_misses.stlb_hit")
        #events.append("l1d_pend_miss.pending_cycles")
        #events.append("mem_inst_retired.all_loads")
        #events.append("mem_inst_retired.all_stores")
        #events.append("mem_load_retired.l2_miss")
        #events.append("mem_load_retired.l2_hit")
        #events.append("mem_load_retired.l3_miss")
        #events.append("mem_load_retired.l3_hit")
        events.append("instructions")
        events.append("cycles")
        #events.append("cache-misses")
        #events.append("branch-misses")
        #events.append("L1-dcache-load-misses")
        #events.append("L1-icache-load-misses")
        #events.append("GHz")
        #events.append("insn per cycle")
        #events.append("seconds time elapsed")
        return events

    @staticmethod
    def get_perf_stat_events():
        ev=[]
        #ev.append("GHz")
        #ev.append("insn per cycle")
        #ev.append("seconds time elapsed")
        ev.append("instructions")
        ev.append("cycles")
        return ev

    def sample(self, timestamp):
        
        iterations_cycle=math.ceil((len(self.events))/4.0) #4 number of available perf counters provided by intel +1 in orer to run perf stat without events
        event_index=self.iteration%iterations_cycle 
        event_index=event_index*4
        
        #if self.iteration%(iterations_cycle-1)==0 and self.iteration!=0:
            #events_str = ','.join(self.events[(event_index-4):-3])
        if self.iteration%(iterations_cycle)==0:
            events_str = ""
        #else:
         #   events_str = ','.join(self.events[(event_index-4):(event_index)])

        if events_str=="":
            cmd = ['sudo', self.perf_path, 'stat', '-a', '-p', self.pid,'sleep', str(self.sampling_length)]
        else:
            cmd = ['sudo', self.perf_path, 'stat', '-a', '-e', events_str,'-p', self.pid,'sleep', str(self.sampling_length)]
        
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        out = result.stdout.decode('utf-8').splitlines() + result.stderr.decode('utf-8').splitlines()
        
        for e in self.events[0:-3]:
            
            for l in out:
                l = l.lstrip()
                m = re.match("(.*)\s+.*\s+{}".format(e), l)
                
                if m:
                    value = m.group(1)
                    self.timeseries[e].append((timestamp, str(float(value.replace(',', '')))))

        for e in self.perf_stats_events:
            for l in out:
                l = l.lstrip()
                if e in l:
                    value=l.split()[-(len(e.split())+1)]
                    if e == "instructions":
                        value=l.split()[-7]
                    elif e == "cycles":
                        value=l.split()[-5]
                    self.timeseries[e].append((timestamp, str(float(value.replace(',', '')))))
              
    # FIXME: Currently, we add a dummy zero sample when we finish sampling. 
    # This helps us to determine the sampling duration later when we analyze the stats
    # It would be nice to have a more clear solution
    def zerosample(self, timestamp):
        for e in self.events:
            self.timeseries[e].append((timestamp, str(0.0)))

    def interrupt_sample(self):
        os.system('sudo pkill -2 sleep')

    def clear(self):
        self.timeseries = {}
        for e in self.events:
            self.timeseries[e] = []

    def report(self):
        return self.timeseries

class MpstatProfiling(EventProfiling):
    def __init__(self, sampling_period=1, sampling_length=1):
        super().__init__(sampling_period, sampling_length)
        self.timeseries = {}
        self.timeseries['cpu_util'] = []

    def sample(self, timestamp):
        cmd = ['mpstat', '1', '1']
        result = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        lines = result.stdout.decode('utf-8').splitlines() + result.stderr.decode('utf-8').splitlines()
        for l in lines:
            if 'Average' in l:
                idle_val = float(l.split()[-1])
                util_val = str(100.00-idle_val)
                self.timeseries['cpu_util'].append((timestamp, util_val))
                return 

    def interrupt_sample(self):
        pass

    def zerosample(self, timestamp):
        pass

    def clear(self):
        self.timeseries = {}
        self.timeseries['cpu_util'] = []

    def report(self):

        return self.timeseries

class StateProfiling(EventProfiling):
    cpuidle_path = '/sys/devices/system/cpu/cpu0/cpuidle/'

    def __init__(self, sampling_period=0):
        super().__init__(sampling_period)
        self.state_names = StateProfiling.power_state_names()
        self.timeseries = {}

    @staticmethod
    def power_state_names():
        cpuidle_path = StateProfiling.cpuidle_path
        if not os.path.exists(cpuidle_path):
            return []
        state_names = []
        states = os.listdir(cpuidle_path)
        states.sort()
        for state in states:
            state_name_path = os.path.join(cpuidle_path, state, 'name')
            with open(state_name_path) as f:
                state_names.append(f.read().strip())
        return state_names

    @staticmethod
    def power_state_metric(cpu_id, state_id, metric):
        cpuidle_path = StateProfiling.cpuidle_path
        if not os.path.exists(cpuidle_path):
            return None
        output = open("/sys/devices/system/cpu/cpu{}/cpuidle/state{}/{}".format(cpu_id, state_id, metric)).read()
        return output.strip()

    def sample_power_state_metric(self, metric, timestamp):
        for cpu_id in range(0, os.cpu_count()):
            for state_id in range(0, len(self.state_names)):
                state_name = self.state_names[state_id]
                key = "CPU{}.{}.{}".format(cpu_id, state_name, metric)
                value = StateProfiling.power_state_metric(cpu_id, state_id, metric)
                self.timeseries.setdefault(key, []).append((timestamp, value))

    def sample(self, timestamp):
        self.sample_power_state_metric('usage', timestamp)
        self.sample_power_state_metric('time', timestamp)

    def interrupt_sample(self):
        pass

    def zerosample(self, timestamp):
        pass

    def clear(self):
        self.timeseries = {}

    def report(self):
        return self.timeseries

class RaplCountersProfiling(EventProfiling):
    raplcounters_path = '/sys/class/powercap/intel-rapl/'   

    def __init__(self, sampling_period=0):
        super().__init__(sampling_period)
        self.domain_names = {}
        self.domain_names = RaplCountersProfiling.power_domain_names()
        self.timeseries = {}

    @staticmethod
    def power_domain_names():
        raplcounters_path = RaplCountersProfiling.raplcounters_path
        if not os.path.exists(raplcounters_path):
            return []
        domain_names = {}
        
        #Find all supported domains of the system
        for root, subdirs, files in os.walk(raplcounters_path):
            for subdir in subdirs:
                if "intel-rapl" in subdir:
                    domain_names[open("{}/{}/{}".format(root, subdir,'name'), "r").read().strip()]= os.path.join(root,subdir,'energy_uj')    
        return domain_names

   
    def sample(self, timestamp):
         for domain in self.domain_names:
                value = open(self.domain_names[domain], "r").read().strip()
                self.timeseries.setdefault(domain, []).append((timestamp, value))
       

    def interrupt_sample(self):
        pass

    def zerosample(self, timestamp):
        pass

    def clear(self):
        self.timeseries = {}

    def report(self):
        return self.timeseries



class pkg_turbostat_profiling(EventProfiling):
    
    def __init__(self, sampling_period=1, sampling_length=1):
        super().__init__(sampling_period, sampling_length)
        self.pkgcstates = self.get_available_pkgcstates()
        logging.info('Available Package C states {}'.format(self.pkgcstates))
        if self.pkgcstates != "\n":
            self.timeseries = {}
            for e in self.pkgcstates:
                package= e.split('%')[0]
                state=e.split('%')[2]
                key = "Package{}.{}.{}".format(package, state, "residency")
                
                self.timeseries[key] = []

    def get_available_pkgcstates(self):
                                    
        #result = call("/users/ganton12/mcperf/package-cstates.sh", shell=True) 
        
        result=subprocess.run(['/users/ganton12/mcperf/scripts/package-cstates.sh'], stdout=subprocess.PIPE)
        line=result.stdout.decode('utf-8').splitlines()
        return line
       
    def sample(self, timestamp):
        #cmd = ['sudo', 'turbostat', '--quiet', '--interval', '9', '&', 'sleep', str(self.sampling_length), ';', 'sudo', 'pkill', 'turbostat' ]
        cmd = ['/users/ganton12/mcperf/scripts/turbostatpackageresidency.sh', str(self.sampling_length)]
        result = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        
        out = result.stdout.decode('utf-8').splitlines()
        
        flag=False
        for s in self.pkgcstates:
            for line in out:
                for l in line.lstrip().split('\t'):
                    #m = re.match("(.*)\s+.*\s+{}".format(s), l)
                    if s.split('%')[2] in l:
                        indexvalue=line.lstrip().split('\t').index(l)
                        flag=True
                        break
                    if flag==True and line.lstrip().split('\t')[0] ==  s.split('%')[0] and line.lstrip().split('\t')[1]=='0':
                        package= s.split('%')[0]
                        state= s.split('%')[2]
                        key = "Package{}.{}.{}".format(package, state, "residency")
                        self.timeseries[key].append((timestamp, str(float(line.lstrip().split('\t')[indexvalue]))))
                        flag=False
                        break
    
    
    # FIXME: Currently, we add a dummy zero sample when we finish sampling. 
    # This helps us to determine the sampling duration later when we analyze the stats
    # It would be nice to have a more clear solution
    def zerosample(self, timestamp):
    
        for e in self.pkgcstates:
            package= e.split('%')[0]
            state=e.split('%')[2]
            key = "Package{}.{}.{}".format(package, state, "residency")
            self.timeseries[key].append((timestamp, str(0.0)))

    def interrupt_sample(self):
        os.system('sudo pkill turbostat')

    def clear(self):
        self.timeseries = {}
        for e in self.pkgcstates:
            package= e.split('%')[0]
            state=e.split('%')[2]
            key = "Package{}.{}.{}".format(package, state, "residency")
            self.timeseries[key] = []

    def report(self):
        return self.timeseries


class ProfilingService:
    def __init__(self, profilers):
        self.profilers = profilers
        
    def start(self):
        
        for p in self.profilers:
            print(p)
            p.start()
           
    def stop(self):
        for p in self.profilers:
            p.stop()
        time.sleep(5)        

    def report(self):
        timeseries = {}
        time.sleep(5)
        for p in self.profilers:
            t = p.report()
            timeseries = {**timeseries, **t}
        return timeseries

    def set(self, kv):
        print(kv)
        

def server(port,perf_iteration):
    #perf_event_profiling = PerfEventProfiling(sampling_period=30,sampling_length=30,iteration=perf_iteration)
    #mpstat_profiling = MpstatProfiling()
    #vtune_pcie = VtunePcieProfiling(sampling_period=30, sampling_length=30)
    pmu_topdown = TopDownProfiling(sampling_period=120, sampling_length=120, iteration=perf_iteration)
   
    #upi_profiling = PcmUpiProfiling(sampling_period=30, sampling_length=30)
    #pcie_profiling = PcmPcieProfiling(sampling_period=120,sampling_length=120)
    #state_profiling = StateProfiling(sampling_period=0)
    #rapl_profiling = RaplCountersProfiling(sampling_period=0)
    #pkg_profiling = pkg_turbostat_profiling(sampling_period=30,sampling_length=30)
    profiling_service = ProfilingService([pmu_topdown])

    hostname = socket.gethostname().split('.')[0]
    server = SimpleXMLRPCServer((hostname, port), allow_none=True)
    server.register_instance(profiling_service)
    logging.info("Listening on port {}...".format(port))
    server.serve_forever()

class StartAction:
    @staticmethod
    def add_parser(subparsers):
        parser = subparsers.add_parser('start', help = "Start profiling")
        parser.set_defaults(func=StartAction.action)

    @staticmethod
    def action(args):
        with xmlrpc.client.ServerProxy("http://{}:{}/".format(args.hostname, args.port)) as proxy:
            proxy.start()

class StopAction:
    @staticmethod
    def add_parser(subparsers):
        parser = subparsers.add_parser('stop', help = "Stop profiling")
        parser.set_defaults(func=StopAction.action)

    @staticmethod
    def action(args):
        with xmlrpc.client.ServerProxy("http://{}:{}/".format(args.hostname, args.port)) as proxy:
            proxy.stop()

class ReportAction:
    @staticmethod
    def add_parser(subparsers):
        parser = subparsers.add_parser('report', help = "Report profiling")
        parser.set_defaults(func=ReportAction.action)
        parser.add_argument(
                    "-d", "--directory", dest='directory',
                    help="directory where to output results")

    @staticmethod
    def action(args):
        with xmlrpc.client.ServerProxy("http://{}:{}/".format(args.hostname, args.port)) as proxy:
            stats = proxy.report()
            if args.directory:
                ReportAction.write_output(stats, args.directory)
            else:
                print(stats)

    @staticmethod
    def write_output(stats, directory):
        if not os.path.exists(directory):
            os.makedirs(directory)        
        for metric_name,timeseries in stats.items():
            metric_file_name = metric_name.replace('/', '-')
            metric_file_path = os.path.join(directory, metric_file_name)
            with open(metric_file_path, 'w') as mf:
                mf.write(metric_name + '\n')
                for val in timeseries:
                    mf.write(','.join(val) + '\n')

class SetAction:
    @staticmethod
    def add_parser(subparsers):
        parser = subparsers.add_parser('set', help = "Set sysfs")
        parser.set_defaults(func=SetAction.action)
        parser.add_argument('-c', dest='command')
        parser.add_argument('rest', nargs=argparse.REMAINDER)

    @staticmethod
    def action(args):
        with xmlrpc.client.ServerProxy("http://{}:{}/".format(args.hostname, args.port)) as proxy:
            proxy.set(args.rest)

def parse_args():
    """Configures and parses command-line arguments"""
    parser = argparse.ArgumentParser(
                    prog = 'profiler',
                    description='profiler',
                    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        "-n", "--hostname", dest='hostname',
        help="profiler server hostname")
    parser.add_argument(
        "-p", "--port", dest='port', type=int, default=8000,
        help="profiler server port")
    parser.add_argument(
        "-v", "--verbose", dest='verbose', action='store_true',
        help="verbose")

    parser.add_argument(
        "-i", "--iteration", dest='perf_iteration', type=int, default=1,
        help="perf iteration to choose the right performance counters")

    subparsers = parser.add_subparsers(dest='subparser_name', help='sub-command help')
    actions = [StartAction, StopAction, ReportAction, SetAction]
    for a in actions:
      a.add_parser(subparsers)

    args = parser.parse_args()
    logging.basicConfig(format='%(levelname)s:%(message)s')

    if args.verbose:
        logging.getLogger('').setLevel(logging.INFO)
    else:
        logging.getLogger('').setLevel(logging.ERROR)

    if args.hostname:
        if 'func' in args:
            args.func(args)
        else:
            raise Exception('Attempt to run in client mode but no command is given')
    else:
        server(args.port,args.perf_iteration)

def real_main():
    parse_args()

def main():
    real_main()
    return
    try:
        real_main()
    except Exception as e:
        logging.error("%s %s" % (e, sys.stderr))
        sys.exit(1)

if __name__ == '__main__':
    main()
