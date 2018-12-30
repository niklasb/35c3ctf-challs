Big shoutout to joernchen for the challenge idea!

# Ruby build

```
$ git clone https://github.com/ruby/ruby ruby-dbg --depth=2000
$ cd ruby-dbg
$ git checkout 644f2013d637595d9592ad45714788abd8eb6e0e
$ autoconf
$ ./configure CC=clang debugflags='-g2 -O0' optflags='-O0'
$ make -j6
$ sha1sum miniruby
1a0537cd309c9c858efc138386f9b2b62c11ac2e
```

# glibc build

```
$ git clone git://sourceware.org/git/glibc.git
$ cd glibc
$ git checkout 5a74abda201907cafbdabd1debf98890313ff71e
$ mkdir build
$ cd build
$ export CFLAGS='-O3 -g2'
$ ../configure --enable-debug --enable-optimize --disable-experimental-malloc --prefix=`pwd`/out
$ make -j6
$ sha1sum libc.so
e564d503259299a77c7c72ac11750e7d086157b9
```

# Setup

```
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
```

# Fun

Maybe this helps: https://github.com/niklasb/rubyfun
