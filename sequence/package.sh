#!/bin/bash
CHALL=sequence
cd "$(dirname "$0")"
rm -rf $CHALL $CHALL.tar.gz $CHALL-*.tar.gz
mkdir -p $CHALL
cp README.md miniruby libc.so challenge.rb ../proof_of_work/pow.py \
  docker/Dockerfile docker/run.sh docker/xinetd.conf \
  $CHALL/
tar czvf $CHALL.tar.gz $CHALL || exit 1
HASH=`md5sum $CHALL.tar.gz | cut -d' ' -f1`
FNAME=$CHALL-$HASH.tar.gz
mv $CHALL.tar.gz $FNAME
scp $FNAME c3score:/home/ctf/sftp-chroot/uploads
rm -rf $CHALL $CHALL.tar.gz
echo
echo "https://35c3ctf.ccc.ac/uploads/$FNAME"
