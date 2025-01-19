CFLAGS=-O2 -Wall -Wextra -D_FORTIFY_SOURCE=2 -fstack-protector-strong -fstack-clash-protection -fPIE -pie -fPIC -Wl,-z,relro -Wl,-z,now -Wl,-z,noexecstack -Wl,-z,separate-code

all: target

target: target.c
	clang $(CFLAGS) -fprofile-instr-generate -fcoverage-mapping -o target.cov.out target.c
	../../AFLplusplus/afl-clang-lto $(CFLAGS) -o target.out target.c

clean:
	$(RM) *.out *.profraw
