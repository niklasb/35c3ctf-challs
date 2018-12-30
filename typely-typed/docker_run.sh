#!/bin/bash
docker run -it --rm -p 127.0.0.1:9000:80 --name typely 35c3/typely "$@"
