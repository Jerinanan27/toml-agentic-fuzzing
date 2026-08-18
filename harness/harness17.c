#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "tomlc17.h"

#define EXIT_ACCEPTED 0
#define EXIT_REJECTED 50
#define EXIT_HARNESS_ERROR 51

int main(void) {
    size_t capacity = 4096;
    size_t length = 0;
    char *buf = malloc(capacity);
    if (!buf) {
        fprintf(stderr, "harness: out of memory\n");
        return EXIT_HARNESS_ERROR;
    }

    size_t n;
    while ((n = fread(buf + length, 1, capacity - length, stdin)) > 0) {
        length += n;
        if (length >= capacity) {
            capacity *= 2;
            char *bigger = realloc(buf, capacity);
            if (!bigger) {
                free(buf);
                fprintf(stderr, "harness: out of memory\n");
                return EXIT_HARNESS_ERROR;
            }
            buf = bigger;
        }
    }

    /* tomlc17 takes a length, so no NUL-termination needed and
       embedded NULs are fine - the interface improved over tomlc99. */
    toml_result_t result = toml_parse(buf, (int)length);
    free(buf);

    if (!result.ok) {
        fprintf(stderr, "reject: %s\n", result.errmsg);
        toml_free(result);
        return EXIT_REJECTED;
    }

    toml_free(result);
    return EXIT_ACCEPTED;
}