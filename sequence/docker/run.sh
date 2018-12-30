#!/bin/bash
DIFFICULTY=30000000
python /chall/pow.py ask $DIFFICULTY || exit 1
LD_LIBRARY_PATH=/chall exec /chall/miniruby /chall/challenge.rb
