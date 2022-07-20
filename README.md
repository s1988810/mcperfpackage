<<<<<<< HEAD
# Installing Dependencies 

In order to be able to run profiler for top down analysis you have to install manually the pmu - tools (at the moment the installation procedure is not automated for this part)
```
git clone https://github.com/andikleen/pmu-tools
````
In order to be able to take SoCwatch measuremts(i.e pc1 residency measurements), you have to install SoCwatch (at the moment the installation procedure is not automated for this part). Use the following link for installation guide: 
https://www.intel.com/content/www/us/en/developer/tools/oneapi/vtune-profiler-download.html?operatingsystem=linux

In order to be able to take Vtune measuremts(i.e IO traffic), you have to install vtune (at the moment the installation procedure is not automated for this part). Use the following link for installation guide: 
https://www.intel.com/content/www/us/en/developer/tools/oneapi/vtune-profiler-download.html?operatingsystem=linux


To take bandwidth related measurements (PCIe, UPI, memory etc) there is another way, you have to install pcm-tools. Have in mind that vtune seems to generate more accurate measurements. 

```
sudo apt install cmake
git clone https://github.com/opcm/pcm.git
mkdir build
cd build
cmake ..
cmake --build .
```

# Profiler related Comments:
 



=======
>>>>>>> 7d8bca31e8c21710a7fd901c60516d903ac87e5e
# Running experiments

```
./mcperf.sh install_dep
./mcperf.sh build_install
python3 run_experiment.py BATCH_NAME
```

# Analyzing data
```
python3 pull.py HOSTNAME
python3 analyze.py data/BATCH_NAME
```

# Building kernel packages on Ubuntu 18.04

```
sudo apt update
sudo apt-get install build-essential linux-source bc kmod cpio flex libncurses5-dev libelf-dev libssl-dev
sudo chmod a+rwx /mydata
wget https://cdn.kernel.org/pub/linux/kernel/v4.x/linux-4.15.18.tar.xz
tar -xf linux-4.15.18.tar.xz
cp /boot/config-4.15.0-159-generic .config
```

Edit .config

```
CONFIG_LOCALVERSION="c1-2-2-c1e-10-20"
CONFIG_SYSTEM_TRUSTED_KEYS=""
```

```
make oldconfig
```

Edit ./drivers/idle/intel_idle.c:661

```
make -j`nproc` bindeb-pkg
```

```
sudo dpkg -i linux-headers-4.15.18-c1-2-2-c1e-10-20_4.15.18-c1-2-2-c1e-10-20-1_amd64.deb linux-image-4.15.18-c1-2-2-c1e-10-20_4.15.18-c1-2-2-c1e-10-20-1_amd64.deb
sudo dpkg -i linux-headers-4.15.18-c1-1-1-c1e-10-20_4.15.18-c1-1-1-c1e-10-20-2_amd64.deb linux-image-4.15.18-c1-1-1-c1e-10-20_4.15.18-c1-1-1-c1e-10-20-2_amd64.deb
sudo dpkg -i linux-headers-4.15.18-c1-1-1-c1e-05-20_4.15.18-c1-1-1-c1e-05-20-3_amd64.deb linux-image-4.15.18-c1-1-1-c1e-05-20_4.15.18-c1-1-1-c1e-05-20-3_amd64.deb
```

# Building kernel tools

```
make -C tools/perf
```

```
sudo apt install pciutils-dev
make -C tools/power/cpupower
```

# Configuring kernel

```
ssh -n node1 'cd ~/mcperf; sudo python3 configure.py -v --kernelconfig=baseline -v'
```

# Setting and checking uncore freq

[Setting uncore freq](https://www.linkedin.com/pulse/manually-setting-uncore-frequency-intel-cpus-johannes-hofmann/)

```
sudo likwid-perfctr -C 0-2 -g CLOCK sleep 1
```


# Installing Dependencies 

* In order to be able to run profiler for top down analysis you have to install manually the pmu - tools (at the moment the installation procedure is not automated for this part)
```
git clone https://github.com/andikleen/pmu-tools
````
* In order to be able to take SoCwatch measuremts(i.e pc1 residency measurements), you have to install SoCwatch (at the moment the installation procedure is not automated for this part). Use the following link for installation guide: 
https://www.intel.com/content/www/us/en/developer/tools/oneapi/vtune-profiler-download.html?operatingsystem=linux

* In order to be able to take Vtune measuremts(i.e IO traffic), you have to install vtune (at the moment the installation procedure is not automated for this part). Use the following link for installation guide: 
https://www.intel.com/content/www/us/en/developer/tools/oneapi/vtune-profiler-download.html?operatingsystem=linux


* To take bandwidth related measurements (PCIe, UPI, memory etc) there is another way, you have to install pcm-tools. Have in mind that vtune seems to generate more accurate measurements. 

```
sudo apt install cmake
git clone https://github.com/opcm/pcm.git
mkdir build
cd build
cmake ..
cmake --build .
```

# Profiler Parameters

* Profiler supports the following measurements: rapl power measurements, c-states residency, IO bandwidth (pcm), top down analysis (pmu), utilization (mpstat), performance counters (perf).
* To choose which profiler metrics to measure, change the source code of profiler.py function: server() line:  profiling_service = ProfilingService([ state_profiling, rapl_profiling, pmu_topdown]) with the objects of the preferred metrics.
* Write now some metrics are measured from the profiler and some others from the run_experiment. The run_experiment metrics are anything related with vtune-socwatch (pc1 residency and IO bandwidth) and also all metrics related with memcached, like client and server side latency.


