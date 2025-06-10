#include <ctype.h>
#include <errno.h>
#include <stdio.h>
#include <unistd.h>
#include <string.h>

#define EXIT_FAILURE -1
#define EXIT_SUCCESS 0
#define MAX_INPUT_SIZE 4096

typedef void func(void);

int main(int argc, char **argv) {
    unsigned char buf[MAX_INPUT_SIZE];
    int len;
    unsigned long addr;

    // Wait for input on stdin
    for (len = 0; len == 0; len = read(STDIN_FILENO, buf, sizeof(buf))) {
    }

    if (len < 0) {
        return len;
    } else if (len < 8) {
        return EXIT_FAILURE;
    }

    addr = *((unsigned long *)&buf);
    printf("Got header %p\n", (void *)addr);
    if (addr != 0xdeadbeef) {
        return EXIT_FAILURE;
    }

    func *f = (func *)addr;
    f();

    return EXIT_SUCCESS;
}
