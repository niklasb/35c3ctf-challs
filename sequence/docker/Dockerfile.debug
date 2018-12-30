FROM 35c3/instruct
RUN apt-get -y update
RUN apt-get -y install git
RUN cd /root && git clone https://github.com/niklasb/gdbinit && cd gdbinit && ./setup.sh

CMD xinetd -d -dontfork
