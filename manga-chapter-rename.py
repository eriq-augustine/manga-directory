#!/usr/bin/env python3

'''
Rename pages in chapter directories.
This assumes:
 - The parent directory is correctly named (as a chapter).
 - The directory only contains pages (image files).
 - The pages' lexicographic ordering is their page ordering.

Existing page numbers will not be preserved.
'''

import argparse
import os
import shutil

def renameChapter(basePath, interactive):
    basePath = os.path.abspath(basePath)
    if (not os.path.isdir(basePath)):
        print("ERROR: Specified path is not a directory: '%s'." % (basePath))
        return False

    baseName = os.path.basename(basePath)

    renames = []
    for dirent in sorted(os.listdir(basePath)):
        pagePath = os.path.join(basePath, dirent)
        if (not os.path.isfile(pagePath)):
            print("ERROR: Specified directory contains something that is not a file: '%s'." % (pagePath))

        ext = os.path.splitext(dirent)[-1]

        renames.append((dirent, "%s p%03d%s" % (baseName, len(renames) + 1, ext)))

    commit = True

    if (interactive):
        print(basePath)
        for (original, rename) in renames:
            print("    '%s' -> '%s'" % (original, rename))

        response = input('Do rename? (Y / N): ').lower()
        if (response.startswith('y')):
            commit = True
        elif (response.startswith('n')):
            commit = False
        else:
            print("Unknwon response '%s', not doing rename." % (response))
            commit = False

    if (commit):
        for (original, rename) in renames:
            originalPath = os.path.join(basePath, original)
            newPath = os.path.join(basePath, rename)

            shutil.move(originalPath, newPath)

    return True

def main(args):
    for path in args.paths:
        renameChapter(path, args.interactive)

def _load_args():
    parser = argparse.ArgumentParser(description = 'Rename pages in chapter directories')

    parser.add_argument('-i', '--interactive', dest = 'interactive',
            action = 'store_true', default = False,
            help = 'ask before each batch of operations')

    parser.add_argument('paths',
            metavar = 'PATH', type = str, nargs = '+',
            help = 'a chapter directory')

    return parser.parse_args()

if (__name__ == '__main__'):
    main(_load_args())
