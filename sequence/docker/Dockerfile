FROM ubuntu:18.10
RUN apt-get -y update
RUN apt-get -y install xinetd gdb python-minimal

RUN groupadd -g 1000 chall && useradd -g chall -m -u 1000 chall -s /bin/bash

RUN mkdir /chall

COPY miniruby /chall/miniruby
COPY libc.so /chall/libc.so
COPY challenge.rb /chall/challenge.rb
COPY xinetd.conf /etc/xinetd.d/chall
COPY run.sh /chall/run.sh
COPY pow.py /chall/pow.py
COPY flag /flag

RUN chmod +x /chall/miniruby /chall/run.sh
RUN ln -s /chall/libc.so /chall/libc.so.6

CMD xinetd -d -dontfork
