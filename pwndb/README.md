Challenge is running on fully updated Windows 10 RS5 (Build 1809). You
may try to use one of the images from [1], they did not work for us but
good luck.

If you need more information about the remote system, please ask in IRC.

Challenge is running with low IL and served via

    socat -T180 tcp4-l:1337,fork exec:./pwndb.exe

in a WSL bash shell.

Also, because Windows 10 sucks as a server system (although surprisingly 1809
sucks way less than 1709), we might kill all pwndb.exe processes every 10 minutes
or so. So if your exploit fails, please try again. If your exploit takes much
longer than a few minutes, please let us know and we might be able to disable
the watchdog temporarily.

There is no intended bug in the SQL parser, so you may just trust the
sqlparser.h file. Oh and we noticed that people were exploiting a red herring
bug we thought was unexploitable. Thanks for telling us, it's fixed.

Flag is in `C:\flag.txt`. Don't assume the challenge process is allowed anything
other than to read this file.

--
[1]: https://developer.microsoft.com/en-us/windows/downloads/virtual-machines
