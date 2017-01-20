# bacnet_explore

BACpypes has services readPropertyMulti and writePropertyMulti, which are more efficient than read and write services. This project is using BACpypes to write scan function to get the information of points in the buildings,  and sMAP drivers that read/write the value of points. 

BACpypes applications -- BACpypes application have different bacnet services including readProperty, readPropertyMulti, writeProperty, writePropertyMulti, and whois. 

BACpypes scan -- BACpypes scan function read commands from a config file, user can define if scan the whole building system or just a specific subnet or some devices. The scan function use readPropertyMulti to get the information of devices and points, it’s okay if the device doesn’t support segmentation, in that case, the scan function will read 2 points per time to make sure that it won’t lose any data, and if the device support segmentation, it read 50 points each time. If read more points one time, it may cause failure. 
#### run scan function ####
python BACpypes_scan.py

BACpypes driver --The driver uses readPropertyMulti to read the present value of the points and post them on the website.
#### run smap driver ####
sudo /home/.../bin/python /home/.../bin/twistd --logfile=/home/.../twistd.log --pidfile=/home/.../twistd.pid smap /home/.../conf/sdh_s1.ini
