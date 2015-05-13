# Copyright (c) 2014 Sine Nomine Associates
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THE SOFTWARE IS PROVIDED 'AS IS' AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#

import sys
import os
import stat
import re
import cmd
import string
import glob
import subprocess
import traceback

from OpenAFSLibrary.util.download import download
from OpenAFSLibrary.util.partition import create_fake_partition
from OpenAFSLibrary import OpenAFSLibrary

try:
    import settings as old_settings
except:
    old_settings = None

class Setting:
    @staticmethod
    def from_table(table, name):
        row = table[name]
        if len(row) == 3:
            return Setting(name, t=row[0], dv=row[1], desc=row[2])
        if len(row) == 4:
            return Setting(name, t=row[0], dv=row[1], desc=row[2], e=row[3])
        assert("Unexpected number of elements in settings table! name=%s" % name)

    def __init__(self, name, t='name', value=None, dv=None, desc=None, e=()):
        self.name = name
        self.value = None
        self.t = t
        self.dv = dv
        self.desc = desc
        self.e = e
        if not value is None:
            self.set(value)
        elif not dv is None:
            self.set(dv)

    def set(self, value):
        if self.t == 'bool':
            if value is None:
                self.value = False
            elif value.lower() in ['1', 'yes', 'true']:
                self.value = True
            elif value.lower() in ['0', 'no', 'false']:
                self.value = False
            else:
                sys.stderr.write("Expected 'true' or 'false' for %s.\n" % (self.name))
        elif self.t == 'int':
            self.value = int(value)
        else:
            self.value = value

    def reset(self):
        if not self.dv is None:
            self.set(self.dv)

    def emit(self, f):
        if self.t == 'bool':
            if self.value:
                v = 'True'
            else:
                v = 'False'
        elif self.t == 'int':
            if self.value:
                v = '%d' % self.value
            else:
                v = '0'
        else:
            if self.value:
                v = '"%s"' % self.value.replace('"', '\\"')
            else:
                v = '""'
        f.write("%-24s = %s\n" % (self.name, v))

class Settings:
    """The collection of setting values."""
    def __init__(self, root, table):
        """Intialize the setting collection.

        Start with default values and then overlay with the
        values in the existing settings.py file (if one).
        This preserves any extra user defined values in
        settings.py, even if they are not in the settings table."""
        self.saved = False
        self.settings = dict()
        self.root = root
        self.table = table
        assert(root is not None)
        assert(table is not None)

        # Set default values.
        for name in table.keys():
            self.settings[name] = Setting.from_table(table, name)

        # Overlay current values:
        if old_settings:
            for name in dir(old_settings):
                if name.startswith('__') and name.endswith('__'):
                    continue  # skip module attrs
                value = "%s" % (getattr(old_settings, name))
                if name in self.settings:
                    self.settings[name].set(value)
                else:
                    self.settings[name] = Setting(name, value=value)

    def get_dict(self):
        settings = {}
        for name in self.settings.keys():
            settings[name] = self.settings[name].value
        return settings

    def list(self):
        seen = {}
        for name in sorted(self.settings.keys()):
            value = self.settings[name].value
            if value == '':
               value = '(empty)'
            sys.stdout.write("%-18s  %s\n" % (name, value))

    def set(self, name, value):
        name = name.upper()
        if name in self.settings:
            self.settings[name].set(value)
        else:
            self.settings[name] = Setting(name, value=value)
        self.save()

    def get(self, name):
        name = name.upper()
        value = None
        if name in self.settings:
            value = self.settings[name].value
        return value

    def unset(self, name):
        name = name.upper()
        if name in self.settings:
            del self.settings[name.upper()]
        self.save()

    def reset(self):
        for setting in self.settings.values():
            setting.reset()
        self.save()

    def save(self):
        f = open(os.path.join(self.root, "settings.py"), "w+")
        f.write("# OpenAFS RobotTest Settings\n")
        f.write("# Please use afs-robotest-setup to change this file.\n")
        for name in sorted(self.settings.keys()):
            setting = self.settings[name]
            setting.emit(f)
        f.close()
        self.saved = True

class SetupShell(cmd.Cmd):
    """Console interface to setup the OpenAFS Robotest harness."""

    def __init__(self, script=None, settings=None, root=".", table={}):
        """Initialize the command interpreter.

        Read commands from the open filehandle if given, otherwise read
        commands from stdin.  Show the interactive prompt if getting
        input from a terminal. This is done to support reading commands
        from a pipeline.
        """
        if settings:
            self.settings = settings
        else:
            self.settings = Settings(root, table)
        if script is not None:
            # Reading commands from a script file.
            self.scriptfd = open(script, "r")
            self.use_rawinput = False
            self.prompt = ''
            self.intro = ''
            cmd.Cmd.__init__(self, stdin=self.scriptfd)
        elif sys.stdin.isatty():
            # Reading commands from a terminal.
            self.scriptfd = None
            self.prompt = '(setup) '
            self.intro = "OpenAFS RoboTest Setup\nType help for information."
            self.doc_header = "Commands. Type help <command> for syntax"
            cmd.Cmd.__init__(self)
        else:
            # Reading commands from a pipe.
            self.scriptfd = None
            self.prompt = ''
            self.intro = ''
            cmd.Cmd.__init__(self)

    def postloop(self):
        if self.scriptfd:
            self.scriptfd.close()

    def _set(self, name, value):
        """Helper to set a setting value."""
        self.settings.set(name,value)

    def _get(self, name, default=None):
        """Helper to get a setting value."""
        value = self.settings.get(name)
        if not value and default:
            value = default
        return value

    def emptyline(self):
        """Do not repeat the last command."""
        pass

    def default(self, line):
        """Skip comment lines."""
        if not line.startswith("#"):
            cmd.Cmd.default(self, line)

    def _complete_value(self, text, values):
        """Helper for tab completion of a set of strings."""
        if text:
            completions = [v for v in values if v.startswith(text)]
        else:
            completions = values
        return completions

    def _complete_filename(self, text, line, begidx, endidx):
        """Helper for filename completion.

        Only the 'text' portion of the pathname is returned in the
        completion list. The underlying readline module parses
        the line into arguments with slashes and other separators, so
        we must use the 'line' string, 'begidx', and 'endidx' to determine
        the fixed portion of the argument, which mush not be included
        in the completions.

        Slashes are appended to directories to make it clear which
        completions are directories. This also reduces the number of
        tabs you need to hit while traversing directories.
        """
        arg_index = line.rfind(" ", 0, begidx)
        if arg_index == -1:
            return
        else:
           arg_index += 1
        fixed = line[arg_index:begidx]    # fixed portion of the argument
        arg = line[arg_index:endidx]      # arg is fixed + text
        completions = []
        for path in glob.glob(arg + '*'):
            if os.path.isdir(path) and path[-1] != os.sep:
                path += os.sep
            completions.append(path.replace(fixed, "", 1))
        return completions

    def do_quit(self, line):
        """Quit this program.

        syntax: quit"""
        self.settings.save()
        return True
    do_EOF = do_quit   # end of file implies quit

    def do_help(self, arg):
        """Display command help.

        syntax: help [<command>]"""
        if arg:
            try:
                doc = getattr(self, "do_%s" % arg).__doc__
            except AttributeError:
                doc = None
            if doc:
                for line in doc.splitlines():
                    print line.replace(" "*8, "", 1)
            else:
                print "No help found for '%s'." % (arg)
        else:
            print self.doc_header
            print self.ruler*60
            # Overridden methods can be listed multiple times. Create
            # a unique list of do_ methods.
            names = {}
            for name in self.get_names():
                if name=="do_EOF":
                    continue
                if name.startswith("do_"):
                    names[name] = 1
            for name in sorted(names.keys()):
                doc = getattr(self, name).__doc__
                if doc:
                    desc = doc.split('\n')[0].strip()
                    print "%-8s  %s" % (name[3:], desc)

    def do_shell(self, line):
        """Run a command using the shell.

        syntax: shell <command-line>
        alias: ! <command-line>"""
        subprocess.call(line, shell=True)

    def do_call(self, line):
        """Execute commands in a file.

        syntax: call <filename>"""
        args = line.split()
        if len(args) != 1:
            print "Missing <filename> argument."
            return
        filename = args[0].strip()
        try:
            shell = SetupShell(script=filename, settings=self.settings, table=self.table)
        except IOError as e:
            sys.stderr.write("Unable to open input-file %s: %s\n" % (filename))
            return
        shell.cmdloop()
    def complete_call(self, text, line, begidx, endidx):
        return self._complete_filename(text, line, begidx, endidx)

    def do_list(self, line):
        """List setting names and values.

        syntax: list"""
        self.settings.list()

    def do_set(self, line):
        """Assign a setting value.

        syntax: set <name> <value>"""
        name,value,line = self.parseline(line)
        if not name:
            print "Missing <name> argument."
            return
        if not value:
            print "Missing <value> argument."
        self.settings.set(name, value)
    def complete_set(self, text, line, begidx, endidx):
        m = re.match(r'set\s+(\w*)$', line)
        if m:
            name = m.group(1)
            if re.match(r'[a-z_]+$', name):
                names = [n.lower() for n in self.settings.table.keys()]
            else:
                names = self.settings.table.keys()
            return self._complete_value(text, names)
        m = re.match(r'set\s+(\w+)\s+\S*$', line)
        if m:
            name = m.group(1).upper()
            if name in self.settings.table:
                row = self.settings.table[name]
                t = row[0]
                if t == 'path':
                    return self._complete_filename(text, line, begidx, endidx)
                elif t == 'bool':
                    return self._complete_value(text, ['true', 'false'])
                elif t == 'enum' and len(row) > 3:
                    return self._complete_value(text, row[3])

    def do_reset(self, line):
        """Reset all settings to default values.

        syntax: reset"""
        self.settings.reset()

    def do_makepart(self, line):
        """Create a fake fileserver partition.

        syntax: makepart <id>
        where <id> is a..z, aa..iv"""
        args = line.split()
        if len(args) != 1:
            print "Missing partition id argument."
            return
        try:
            create_fake_partition(args[0])
        except Exception as e:
            sys.stderr.write("Fail: %s\n" % (e))

    def do_genkey(self, line):
        """Add a kerberos principal then write the keys to a keytab file.

        syntax: genkey afs|user|admin [<enctype>]"""
        args = line.split()
        if len(args) == 1:
            args.append(None)
        if len(args) != 2:
            print "Missing key type argument."
            return
        kind,enctype = args
        if kind == 'afs':
            self._gen_afs_key(enctype)
        elif kind == 'user':
            self._gen_user_key()
        elif kind == 'admin':
            self._gen_admin_key()
        else:
            print "Unknown key type argument."
    def complete_genkey(self, text, line, begidx, endidx):
        return self._complete_value(text, ['afs','user','admin'])

    def _gen_afs_key(self, enctype):
        """Helper to create the AFS service key and keytab."""
        keywords = OpenAFSLibrary()
        akimpersonate = self._get("AFS_AKIMPERSONATE")
        if not enctype:
            enctype = self._get("KRB_AFS_ENCTYPE", 'aes256-cts-hmac-sha1-96')
        keytab = self._get("KRB_AFS_KEYTAB", './site/afs.keytab')
        cell = self._get("AFS_CELL")
        realm = self._get("KRB_REALM")
        verbose = self._get("KRB_VERBOSE")
        if not cell or not realm:
            sys.stderr.write("AFS_CELL and KRB_REALM are required.\n")
            return
        try:
            keywords.create_service_keytab(keytab, cell, realm, enctype, akimpersonate=akimpersonate)
        except:
            sys.stderr.write("Failed to create keytab!")
            traceback.print_exc(file=sys.stderr)
            return
        self._set("KRB_AFS_KEYTAB", keytab)
        self._set("KRB_AFS_ENCTYPE", enctype)

    def _gen_user_key(self):
        """Helper to create the user principal and keytab."""
        keywords = OpenAFSLibrary()
        realm = self._get("KRB_REALM")
        principal = self._get("AFS_USER", "robotest")
        keytab = self._get("KRB_USER_KEYTAB", "./site/user.keytab")
        verbose = self._get("KRB_VERBOSE")
        if not realm:
            sys.stderr.write("KRB_REALM is required.\n")
            return
        try:
            keywords.create_user_keytab(keytab, principal, realm)
        except:
            sys.stderr.write("Failed to create keytab!")
            traceback.print_exc(file=sys.stderr)
            return
        self._set("AFS_USER", principal)
        self._set("KRB_USER_KEYTAB", keytab)

    def _gen_admin_key(self):
        """Helper to create the admin principal and keytab."""
        keywords = OpenAFSLibrary()
        realm = self._get("KRB_REALM")
        principal = self._get("AFS_ADMIN", "robotest/admin")
        keytab = self._get("KRB_ADMIN_KEYTAB", "./site/admin.keytab")
        verbose = self._get("KRB_VERBOSE")
        if not realm:
            sys.stderr.write("KRB_REALM is required.\n")
            return
        try:
            keywords.create_user_keytab(keytab, principal, realm)
        except:
            sys.stderr.write("Failed to create keytab!")
            traceback.print_exc(file=sys.stderr)
            return
        self._set("AFS_ADMIN", principal)
        self._set("KRB_ADMIN_KEYTAB", keytab)

    def do_getrpms(self, line):
        """Download RPM files.

        syntax: getrpms <version> <platform> <directory>
        where: <version> is the openafs version number; e.g. 1.6.10
               <platform> is one of: rhel5, rhel6, openSUSE_12.3
               <directory> is the download destination; e.g. site/rpms"""
        args = line.split()
        if len(args) != 3:
            print "Missing command arguments."
            return
        version,platform,directory = args
        options = {
            'dryrun': False,
            'directory': directory,
        }
        try:
            status = download(version, platform, **options)
        except Exception as e:
            sys.stderr.write("Fail: %s\n" % e.message)
            return
        self._set('RPM_AFSVERSION', version)
        self._set('RPM_PACKAGE_DIR', directory)
        # Determine the release number from the downloaded filenames.
        afsrelease = None
        for f in status['files']:
            m = re.match(r'openafs-\d+\.\d+\.\d+\-(\d+)\..*', os.path.basename(f))
            if m:
                afsrelease = m.group(1)
        if afsrelease:
            self._set('RPM_AFSRELEASE', afsrelease)
        else:
            sys.stderr.write("Failed to find rpm release!\n")

