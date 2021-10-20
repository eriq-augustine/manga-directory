#!/usr/bin/env python3

import argparse
import cmd
import os
import re
import readline
import shutil
import sys

DIRECTORY_REGEX   = re.compile(r'^(.+) v(\d{3}) c(\d{3}[a-z]?)$')
ARCHIVE_REGEX     = re.compile(r'^(.+) v(\d{3}) c(\d{3}[a-z]?)\.(cbz)$')
PAGE_REGEX        = re.compile(r'^(.+) v(\d{3}) c(\d{3}[a-z]?) p(\d{3}(?:-\d{3})?[a-z]?)\.(jpg|png|webp)$')
PAGE_NUMBER_REGEX = re.compile(r'(\d+)(?:-(\d+))?([a-z])?')

CHECKMARK = '✓'

ACTION_RENAME = 'R'
ACTION_IGNORE = 'I'
ACTION_DELETE = 'D'

class InteractiveMode(cmd.Cmd):
    def __init__(self, basePath, renames):
        super().__init__()

        self.intro = "Editing directory '%s'. Type 'help' or '?' for help." % (basePath)
        self.prompt = '> '

        self.basePath = basePath
        self.baseName = os.path.basename(self.basePath)
        self.renames = renames
        self.actions = [ACTION_RENAME] * len(self.renames)

    def do_bulk(self, arg):
        arg = arg.strip()
        if (arg == ''):
            print('ERROR: Found no pattern for bulk rename.')
            return

        for i in range(len(self.renames)):
            original, newName = self.renames[i]
            ext = os.path.splitext(original)[-1]

            match = re.search(arg, original)
            if (match is None or len(match.groups()) != 1):
                continue

            paddedNumber = self._parseAndPad(match.group(1))
            if (paddedNumber is None):
                continue

            self.renames[i][1] = "%s p%s%s" % (self.baseName, paddedNumber, ext)

    # Take in some text that is supposed to be a page number and return a padded version.
    # Note that "page numbers" are not just digits, they can have a dash and letters.
    def _parseAndPad(self, text):
        text = text.strip()

        match = PAGE_NUMBER_REGEX.match(text)
        if (match is None):
            return None

        text = "%03d" % (int(match.group(1)))

        if (match.group(2) is not None):
            text += "-%03d" % (int(match.group(2)))

        if (match.group(3) is not None):
            text += match.group(3)

        return text

    def do_delete(self, arg):
        index, arg = self._parseIndex(arg)
        if (index is None):
            return

        path = os.path.join(self.basePath, self.renames[index][0])

        print("Index %d (%s) marked for delete." % (index, path))
        self.actions[index] = ACTION_DELETE

    def do_ignore(self, arg):
        index, arg = self._parseIndex(arg)
        if (index is None):
            return

        print('Ignoring index %d.' % (index))
        self.actions[index] = ACTION_IGNORE

    def do_help(self, arg):
        print('? / (h)elp - Display this prompt.')
        print('(d)elete   - Delete a single entry from disk.')
        print('(i)gnore   - Ignore a single entry (remove it from the list of renames).')
        print('(p)rint    - Print all the current renames.')
        print('(q)uit     - Quit out of interactive mode without writing/saving the results.')
        print('(r)ename   - Rename a single entry.')
        print('(w)rite    - Write all the renames to disk and quit interactive mode.')
        print('(b)ulk     - Take a given regex and register new renames for all entries.')
        print('             The pattern must capture the page number in the first capture group.')
        print('             re.search is used.')
        print('             On a failed match, no change will be made to the entry.')
        print('             Even entries marked for ignore or deletion will get their rename changed, but their action will remain.')

    def do_print(self, arg):
        for i in range(len(self.renames)):
            action = self.actions[i]
            original, newName = self.renames[i]

            if (action == ACTION_RENAME):
                mark = action
                if (original == newName):
                    mark = CHECKMARK

                print("    %03d (%s) '%s' -> '%s'" % (i, mark, original, newName))
            else:
                print("    %03d (%s) '%s'" % (i, action, original))

    def do_quit(self, arg):
        print('Quitting without writting renames.')
        return True

    def do_rename(self, arg):
        index, arg = self._parseIndex(arg)
        if (index is None):
            return

        if (arg is None):
            print('ERROR: No new name specified.')
            return

        print("Renaming index %d: '%s' -> '%s'." % (index, self.renames[index][1], arg))
        self.actions[index] = ACTION_RENAME
        self.renames[index][1] = arg

    def do_write(self, arg):
        self._commit()
        print('Renames committed to disk.')
        return True

    def do_EOF(self, arg):
        return self.do_quit(None)

    def precmd(self, line):
        return line.strip()

    # Write actions to disk.
    def _commit(self):
        for i in range(len(self.renames)):
            action = self.actions[i]
            original, newName = self.renames[i]

            originalPath = os.path.join(self.basePath, original)
            newPath = os.path.join(self.basePath, newName)

            if (action == ACTION_RENAME and original != newName):
                shutil.move(originalPath, newPath)
            elif (action == ACTION_DELETE):
                self._remove(originalPath)

    def _remove(self, path):
        if (os.path.isfile(path) or os.path.islink(path)):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        else:
            raise ValueError("Path %s is not a file, link, or dir." % (path))

    def _parseIndex(self, arg):
        match = re.match(r'^(-?\d+)\s*.*$', arg)
        if (match is None):
            print('ERROR: Expecting index.')
            return (None, arg)

        index = int(match.group(1))
        arg = arg.removeprefix(match.group(1)).strip()

        if (index < 0 or index >= len(self.renames)):
            print("ERROR: Index (%d) out of range [0, %d)." % (index, len(self.renames)))
            return (None, arg)

        if (self.renames[index] is None):
            print('ERROR: Index %d is ignored.' % (index))
            return (None, arg)

        return (index, arg)

# Make useful aliases (short and caps) for the commands.
for entry in dir(InteractiveMode):
    if (not entry.startswith('do_') or entry == 'do_EOF'):
        continue

    basename = entry.removeprefix('do_')

    setattr(InteractiveMode, 'do_' + basename.upper(), getattr(InteractiveMode, entry))
    setattr(InteractiveMode, 'do_' + basename[0], getattr(InteractiveMode, entry))
    setattr(InteractiveMode, 'do_' + basename[0].upper(), getattr(InteractiveMode, entry))

def interactiveMode(basePath, renames):
    InteractiveMode(basePath, renames).cmdloop()

def editDir(basePath):
    renames = []

    baseName = os.path.basename(basePath)

    for dirent in sorted(os.listdir(basePath)):
        path = os.path.join(basePath, dirent)

        if (os.path.isfile(path)):
            # If this is a non-archive file, assume it is a page.

            ext = os.path.splitext(dirent)[-1]

            match = PAGE_REGEX.match(dirent)

            if (ext[1:] == 'cbz'):
                renames.append([dirent, dirent])
            elif (match is not None):
                renames.append([dirent, dirent])
            else:
                renames.append([dirent, "%s p%03d%s" % (baseName, len(renames) + 1, ext)])
        else:
            # If this is a directory, assume it is a chapter.

            match = DIRECTORY_REGEX.match(dirent)
            if (match is not None):
                renames.append([dirent, dirent])
            else:
                renames.append([dirent, "%s c%03d" % (baseName, len(renames) + 1)])

    interactiveMode(basePath, renames)

def editDirs(paths):
    for path in paths:
        editDir(path)

def validateDirs(paths):
    # TODO
    print("TODO")
    return 1

def main(args):
    if (args.interactive):
        return editDirs(args.paths)
    else:
        return validateDirs(args.path)

def _load_args(args):
    parser = argparse.ArgumentParser(description = 'Validate manga directories or interactively edit them.')

    parser.add_argument('-i', '--interactive', dest = 'interactive',
            action = 'store_true', default = False,
            help = 'interactively edit dirents')

    parser.add_argument('paths',
            metavar = 'PATH', type = str, nargs = '+',
            help = 'a manga directory')

    return parser.parse_args()

if (__name__ == '__main__'):
    sys.exit(main(_load_args(sys.argv)))
