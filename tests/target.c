#include <ctype.h>
#include <errno.h>
#include <stdio.h>
#include <unistd.h>
#include <string.h>

#define EXIT_FAILURE -1
#define EXIT_SUCCESS 0
#define MAX_FILE_SIZE 4096

typedef void func(void);

int read_file(char *path, unsigned char *out, int *out_len) {
    FILE *fp;

    fp = fopen(path, "rb");
    if (!fp) {
        fprintf(stderr, "Failed to open file at %s: %s\n", path, strerror(errno));
        return EXIT_FAILURE;
    }

    *out_len = fread(out, 1, MAX_FILE_SIZE, fp);
    if (ferror(fp)) {
        perror("Failed to read certificate");
        return EXIT_FAILURE;
    }
    if (!feof(fp)) {
        fprintf(stderr, "Warning: truncating input file to %d\n", MAX_FILE_SIZE);
    }

    fclose(fp);
    printf("Read %d bytes from %s\n", *out_len, path);
    return EXIT_SUCCESS;
}

int main(int argc, char **argv) {
    unsigned char buf[MAX_FILE_SIZE];
    int len, err;
    unsigned long addr;

    if (argc != 2) {
        printf("Usage: ./target <file path>\n");
        return EXIT_FAILURE;
    }

    err = read_file(argv[1], buf, &len);
    if (err) {
        return err;
    }

    if (len < 8) {
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
