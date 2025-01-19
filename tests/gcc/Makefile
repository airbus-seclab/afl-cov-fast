CFLAGS=-O2 -Wall -Wextra -D_FORTIFY_SOURCE=2 -fstack-protector-strong -fstack-clash-protection -fPIE -pie -fPIC -Wl,-z,relro -Wl,-z,now -Wl,-z,noexecstack -Wl,-z,separate-code

all: target

target: target.c
	gcc $(CFLAGS) --coverage -o target.cov.out target.c
	../../AFLplusplus/afl-gcc-fast $(CFLAGS) -o target.out target.c

clean:
	$(RM) *.out *.gcno *.gcda
