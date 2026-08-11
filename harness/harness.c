#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "toml.h"

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
    while ((n = fread(buf + length, 1, capacity - length - 1, stdin)) > 0) {
        length += n;
        if (length + 1 >= capacity) {
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

    buf[length] = '\0';

    /* toml_parse takes a NUL-terminated char*, with no length parameter, so
       an input containing an embedded NUL would be silently truncated at the
       first zero byte. We would then report results for an input that is not
       the input we generated. Refuse instead, so untestable inputs are
       counted rather than quietly mis-tested. */
    if (memchr(buf, '\0', length) != NULL) {
        free(buf);
        fprintf(stderr, "harness: input contains NUL byte, cannot be tested\n");
        return EXIT_HARNESS_ERROR;
    }

    char errbuf[256];
    toml_table_t *tab = toml_parse(buf, errbuf, sizeof errbuf);
    free(buf);

    if (!tab) {
        fprintf(stderr, "reject: %s\n", errbuf);
        return EXIT_REJECTED;
    }

    toml_free(tab);
    return EXIT_ACCEPTED;
}