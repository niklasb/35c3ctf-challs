.PHONY: clean

pwndb: $(wildcard *.cpp) $(wildcard *.h)
	clang++ -o $@ $(wildcard *.cpp) -Wall -Wpedantic -std=c++14

clean:
	rm -f pwndb
