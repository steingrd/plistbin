#!/bin/bash 

for file in $(ls xml*); do
    binname=$(echo $file | sed -e 's/xml/bin/g')
    plutil -convert binary1 -o $binname $file
done