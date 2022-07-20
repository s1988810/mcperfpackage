#!/bin/bash

if [[ -z $1 ]]; then
    echo "sampling length interval necessary"
	exit
fi

interval=$1
#execute turbostat for sampling length period 
sudo turbostat --quiet --interval $((interval-1)) & sleep $1 ; sudo pkill turbostat
  


