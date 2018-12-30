# Challenge
Can you bypass the patch?  https://hackerone.com/reports/397478

# Solution

There were at least 3, but maybe even 4 bugs introduced in the patch
https://github.com/gabriel/MPMessagePack/commit/c01e974b09d8278696582c40bf73ddf74e7531ad
which are fixed in 2.12.4 (released on the first day of the CTF):

1. Getting the PID of the sender via `xpc_connection_get_pid` is useless
   because the process can be replaced via PID wraparound or outside a
   sandbox with just execve() as described in https://bugs.chromium.org/p/project-zero/issues/detail?id=1223
2. Getting path from PID is racy
3. Getting binary from path is racy
4. Code signing checks *seem* vulnerable to https://www.okta.com/security-blog/2018/06/issues-around-third-party-apple-code-signing-checks/, but I haven't verified this

I wrote exploits for 1 and 3.
