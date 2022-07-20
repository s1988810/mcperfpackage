#for i in {0..2};
#do
   python3 profiler.py -n node1 -i 1 start
   #taskset -c 4 ./spin 10
   sleep 40
   python3 profiler.py -n node1 -i 1 stop
   python3 profiler.py -n node1 report -d ~/data/delete
#done
