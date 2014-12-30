#!/bin/bash

########################################################################
#
# Linux on Hyper-V and Azure Test Code, ver. 1.0.0
# Copyright (c) Microsoft Corporation
#
# All rights reserved.
# Licensed under the Apache License, Version 2.0 (the ""License"");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
#
# THIS CODE IS PROVIDED *AS IS* BASIS, WITHOUT WARRANTIES OR CONDITIONS
# OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING WITHOUT LIMITATION
# ANY IMPLIED WARRANTIES OR CONDITIONS OF TITLE, FITNESS FOR A PARTICULAR
# PURPOSE, MERCHANTABLITY OR NON-INFRINGEMENT.
#
# See the Apache Version 2.0 License for specific language governing
# permissions and limitations under the License.
#
########################################################################

echoerr() { echo "$@" 1>&2; }

VerifyModules()
{
echo "#### Status of Hyper-V Kernel Modules ####\n"
HYPERV_MODULES=(hv_vmbus hv_netvsc hid_hyperv hv_utils hv_storvsc)
PASS="0"
for module in ${HYPERV_MODULES[@]}; do
    module_alt=`echo $module|sed -n s/-/_/p`
    load_status=$( lsmod | grep $module 2>&1)
        module_name=$module
    if [ "$module_alt" != "" ]; then
        # Some of our drivers, such as hid-hyperv.ko, is shown as
        # "hid_hyperv" from lsmod output. We have to replace all
        # "-" to "_".
        load_status=$( lsmod | grep $module_alt 2>&1)
        module_name=$module_alt
    fi

    # load_status=$(modinfo $module 2>&1)
    # Check to see if the module is loaded.  It is if module name
    # contained in the output.
    if [[ $load_status =~ $module_name ]]; then
        echo  " $module : Success"
    else
        echoerr "ERROR: Status: module '$module' is not loaded"
        PASS="1"
    fi
done

#
# Let the caller know everything worked
#
if [ "1" -eq "$PASS" ] ; then
    exit 10
fi
}


VerifyModules

modprobe -r hyperv_fb
if [ $? -eq 0 ]; then
    msg="hyperv_fb could be disabled."
    echoerr "Error: ${msg}"
    exit 30
fi
pass=0
START=$(date +%s)
while [ $pass -lt 500 ]
do
    modprobe -r hv_netvsc
    modprobe hv_netvsc
    modprobe -r hv_utils
    modprobe hv_utils
    sleep 1
    modprobe -r hid_hyperv
    modprobe hid_hyperv
    pass=$((pass+1))
done
echo "Finished testing, bringing up eth0"
touch ~/reload_finished
ifdown eth0
sleep 1
ifup eth0
sleep 1
ifdown eth0
sleep 1
ifup eth0
VerifyModules

exit 0