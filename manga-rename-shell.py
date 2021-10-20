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

TYPE_NONE = 'None'
TYPE_SERIES = 'Series'
TYPE_CHAPTER = 'Chapter'

class RenameShell(cmd.Cmd):
    def __init__(self, basePath):
        super().__init__()

        self.basePath = os.path.abspath(basePath)
        self.baseName = os.path.basename(self.basePath)
        self.dirType = TYPE_NONE

        self.renames = []
        self.actions = []

        self.intro = "Editing directory '%s'. Type 'help' or '?' for help." % (self.basePath)
        self.prompt = "%s > " % (self.basePath)

        self._reload()

    def complete_cd(self, text, line, begidx, endidx):
        text = text.strip()

        entries = []

        for (original, _) in self.renames:
            if (original.startswith(text)):
                entries.append(original)

        return entries

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

    def do_cd(self, arg):
        arg = arg.strip()

        path = arg
        if (not os.path.isabs(path)):
            path = os.path.join(self.basePath, path)

        self.basePath = os.path.abspath(path)
        self.baseName = os.path.basename(self.basePath)

        self._reload()

    def do_edit(self, arg):
        index, arg = self._parseIndex(arg)
        if (index is None):
            return

        if (arg is None):
            print('ERROR: No new name specified.')
            return

        print("Editing rename index %d: '%s' -> '%s'." % (index, self.renames[index][1], arg))
        self.actions[index] = ACTION_RENAME
        self.renames[index][1] = arg

    def do_ignore(self, arg):
        index, arg = self._parseIndex(arg)
        if (index is None):
            return

        print('Ignoring index %d.' % (index))
        self.actions[index] = ACTION_IGNORE

    def do_help(self, arg):
        print('? / help - Display this prompt.')
        print('bulk     - Take a given regex and register new renames for all entries.')
        print('             The pattern must capture the page number in the first capture group.')
        print('             re.search is used.')
        print('             On a failed match, no change will be made to the entry.')
        print('             Even entries marked for ignore or deletion will get their rename changed, but their action will remain.')
        print('cd       - Chance the current working directory.')
        print('rm       - Delete a single entry from disk.')
        print('edit     - Edit a single rename entry.')
        print('ignore   - Ignore a single entry (remove it from the list of renames).')
        print('ls       - List the entries in the current directory.')
        print('quit     - Quit out of interactive mode without writing/saving the results.')
        print('reload   - Reload this directory from disk.')
        print('type     - Set the type for this directory:')
        print('             (n)one, (s)eries, or (c)hapter.')
        print('write    - Write all the renames to disk and quit interactive mode.')

    def do_ls(self, arg):
        print("%s (%s)" % (self.basePath, self.dirType))

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

    def do_reload(self, arg):
        self._reload()
        print('Directory reloaded.')

    def do_rm(self, arg):
        index, arg = self._parseIndex(arg)
        if (index is None):
            return

        path = os.path.join(self.basePath, self.renames[index][0])

        print("Index %d (%s) marked for delete." % (index, path))
        self.actions[index] = ACTION_DELETE

    def do_type(self, arg):
        newType = None

        arg = arg.strip().lower()
        if (arg == '' or arg[0] == TYPE_NONE[0].lower()):
            newType = TYPE_NONE
        elif (arg[0] == TYPE_SERIES[0].lower()):
            newType = TYPE_SERIES
        elif (arg[0] == TYPE_CHAPTER[0].lower()):
            newType = TYPE_CHAPTER
        else:
            print("ERROR: Unknown type '%s'." % (arg))
            return

        print("Setting directory type to %s." % (newType))
        self.dirType = newType

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

    def _createRename(self, original, number):
        ext = os.path.splitext(original)[-1]
        number = self._parseAndPad(number)

        if (self.dirType == TYPE_NONE):
            return original
        elif (self.dirType == TYPE_SERIES):
            return "%s c%s%s" % (self.baseName, number, ext)
        elif (self.dirType == TYPE_CHAPTER):
            return "%s p%s%s" % (self.baseName, number, ext)
        else:
            raise ValueError("Unknown directory type: %s." % (self.dirType))

    # Take in some text that is supposed to be a page number and return a padded version.
    # Note that "page numbers" are not just digits, they can have a dash and letters.
    def _parseAndPad(self, text):
        text = str(text).strip()

        match = PAGE_NUMBER_REGEX.match(text)
        if (match is None):
            return None

        text = "%03d" % (int(match.group(1)))

        if (match.group(2) is not None):
            text += "-%03d" % (int(match.group(2)))

        if (match.group(3) is not None):
            text += match.group(3)

        return text

    def _parseIndex(self, arg):
        arg = str(arg).strip()

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

    def _reload(self):
        self.renames = []

        for dirent in sorted(os.listdir(self.basePath)):
            self.renames.append([dirent, self._createRename(dirent, len(self.renames) + 1)])

        self.actions = [ACTION_RENAME] * len(self.renames)

def main(args):
    RenameShell(args.path[0]).cmdloop()

def _load_args(args):
    parser = argparse.ArgumentParser(description = 'Interactively edit managa directories.')

    parser.add_argument('path',
            metavar = 'PATH', type = str, nargs = 1,
            help = 'a directory')

    return parser.parse_args()

if (__name__ == '__main__'):
    sys.exit(main(_load_args(sys.argv)))
