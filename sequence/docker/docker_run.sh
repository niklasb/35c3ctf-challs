#!/bin/bash
if [[ "$1" == "debug" ]]; then
  docker run -it --rm -p 127.0.0.1:1337:1337 --cap-add sys_ptrace --name instruct 35c3/instruct-debug
else
  docker run -it --rm -p 127.0.0.1:1337:1337 --name instruct 35c3/instruct
fi
