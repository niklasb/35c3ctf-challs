#!/bin/bash
set -e
cp ../miniruby .
cp ../libc.so .
cp ../challenge.rb .
cp ../../proof_of_work/pow.py .
docker build -f Dockerfile -t 35c3/instruct .
#docker build -f Dockerfile.debug -t 35c3/instruct-debug .
