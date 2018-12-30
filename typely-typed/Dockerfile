FROM ubuntu:18.04

RUN apt-get -y update
RUN apt-get -y upgrade
RUN apt-get -y install software-properties-common python3 python3-pip ghc curl git

# solc & node.js
RUN add-apt-repository ppa:ethereum/ethereum
RUN curl -sL https://deb.nodesource.com/setup_10.x | bash -

RUN apt-get -y update
RUN apt-get -y install solc nodejs

ENV C /chall
RUN mkdir $C

# Python & npm packages
COPY package.json $C
RUN cd $C && npm install

COPY requirements.txt $C
RUN pip3 install -r $C/requirements.txt

# files
COPY EvmCompiler.hs $C
COPY flag.txt $C
COPY chain.py compiler.py server.py $C/
COPY *.sol $C/
COPY web $C/web
RUN chmod +x $C/server.py

CMD $C/server.py --chain_timeout 600 --hsk_timeout 40 --max_active 100 \
              --host 0.0.0.0 --port 80 --complexity 0.05
