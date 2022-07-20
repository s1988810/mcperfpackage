#!/bin/bash

if [[ -z $(which rdmsr) ]]; then
    echo "msr-tools is not installed. Running 'sudo apt-get install msr-tools' to install it." >&2
	sudo apt-get install msr-tools
fi


#only for skylake systems
#MSR register MSR_PKG_CST_CONFIG_CONTROL specifies the lowest c state code name for package
# The least 3 significant bits of the value (i.e least hexadecimal bit), specify the lowest package c state
# 000: C0/C1 (no package c states support)
# 001: C2
# 010: C6 (no retention)
# 011: C6 (retention)
# 111: No package c states limits all c states supported by the processor are available


pkg_conf_val=`sudo rdmsr 0xe2`
pkg_conf_bit=${pkg_conf_val:(-1)}

#Calculate also the number of sockets for the current machine
socket=`lscpu | grep Socket | awk '{print $2}'`


case  $pkg_conf_bit  in
    "0")       
		echo ""			
        ;;
    "1")
		pkg_cstates="Pkg%pc2"
        ;;            
    "2")   
		pkg_cstates="Pkg%pc2, Pkg%pc6"
        ;; 
    "3")
		pkg_cstates="Pkg%pc2, Pkg%pc3, Pkg%pc6"
		;;					
esac

j=0
pkg_cstates_final=""

while [[ $j -lt $socket ]]
do
	for i in $(echo $pkg_cstates | sed "s/,/ /g")
	do
		
		echo $j"%"$i
	done
	
	((j=j+1))
	
done



