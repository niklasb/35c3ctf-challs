#!/bin/bash
for i in `seq 1 15`; do
  echo $i; python3 client.py;
  sleep $(($RANDOM % 5));
done;
python3 client.py fail ;
for i in `seq 1 24`; do
  echo TEST $i; python3 client.py;
  sleep $(($RANDOM % 5));
done
