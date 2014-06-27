# Copyright (c) 2014, Sine Nomine Associates
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED 'AS IS' AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#

import os
import sys
import glob
import re
from robot.api import logger
from robot.libraries import OperatingSystem

_DEBUG = False

def _info(msg):
    """ Log an info message. """
    logger.info(msg, also_console=_DEBUG)

def _run(cmd):
    """ Run commands with the RF run keyword.  """
    os = OperatingSystem.OperatingSystem()
    (rc, output) = os.run_and_return_rc_and_output("%s" % (cmd))
    _info("rc=%d" % (rc))
    _info("output=%s" % (output))
    if rc != 0:
        raise AssertionError("command failed (rc=%d)" % (rc))
    return output

def _sudo(cmd):
    """ Run commands with sudo. """
    return _run("sudo -n %s" % (cmd))

class Install:
    """
    A RF test library for installing OpenAFS. Support RPM and
    legacy style binary installs.
    """
    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'

    def installation_setup(self, DIST):
        """
        Detect the type of installation to perform based on the contents
        of the distribution directory.
        """
        _info("installation setup: DIST=%s" % (DIST))
        if not DIST:
            raise ValueError("DIST is not set")
        if not os.path.isdir(DIST):
            raise ValueError("DIST is not directory: %s" % (DIST))
        if glob.glob("%s/openafs-*.rpm" % (DIST)):
            _info("Detected rpm distribution.")
            self._imp = _RpmInstall(DIST)
        elif glob.glob("%s/root.server/usr/afs/bin/bosserver" % (DIST)):
            _info("Detected binary distribution.")
            self._imp = _TransarcInstall(DIST)
        else:
            raise AssertionError("Could not determine distribution type from files in DIST: %s" % (DIST))

    def openafs_client_is_installed(self):
        self._imp.openafs_client_is_installed()

    def openafs_client_is_not_installed(self):
        try:
            self._imp.openafs_client_is_installed()
        except:
            return
        raise AssertionError("OpenAFS client is installed")

    def install_openafs_client(self):
        self._imp.install_openafs_client()

    def remove_openafs_client(self):
        self._imp.remove_openafs_client()

    def openafs_server_is_installed(self):
        self._imp.openafs_server_is_installed()

    def openafs_server_is_not_installed(self):
        try:
            self._imp.openafs_server_is_installed()
        except:
            return
        raise AssertionError("OpenAFS server is installed")

    def install_openafs_server(self):
        self._imp.install_openafs_server()

    def remove_openafs_server(self):
        self._imp.remove_openafs_server()



class _TransarcInstall:
    """
    Installation keywords for legacy-style binary distributions.
    """
    def __init__(self, DIST):
        self.DIST = DIST

    def openafs_client_is_installed(self):
        if not os.path.isdir("/usr/vice/etc"):
            raise AssertionError("Client directory /usr/vice/etc is not present.")
        if not os.path.isdir("/usr/afsws"):
            raise AssertionError("Client directory /usr/afsws is not present.")

    def install_openafs_client(self):
        _sudo("mkdir -p /usr/vice/etc")
        _sudo("cp -r -p %s/root.client/usr/vice/etc /usr/vice" % (self.DIST))
        _sudo("mkdir -p /usr/afsws")
        _sudo("cp -r -p %s/bin /usr/afsws" % (self.DIST))
        _sudo("cp -r -p %s/etc /usr/afsws" % (self.DIST))
        _sudo("cp -r -p %s/include /usr/afsws" % (self.DIST))
        _sudo("cp -r -p %s/lib /usr/afsws" % (self.DIST))
        _sudo("cp -r -p %s/man /usr/afsws" % (self.DIST))

    def remove_openafs_client(self):
        _sudo("rm -rf /usr/vice/etc")
        _sudo("rm -rf /usr/afsws")

    def openafs_server_is_installed(self):
        if not os.path.isdir("/usr/afs/bin"):
            raise AssertionError("Server directory /usr/afs/bin is not present.")

    def install_openafs_server(self):
        _sudo("mkdir -p /usr/afs")
        _sudo("cp -r -p %s/root.server/usr/afs/bin /usr/afs" % (self.DIST))

    def remove_openafs_server(self):
        _sudo("rm -rf /usr/afs/bin")


class _RpmInfo:
    """
    Helper class to determine rpm package components.
    """
    def _redhat_release(self):
        try:
            file = open("/etc/redhat-release", "r")
            release = file.readline().rstrip()
            file.close()
        except:
            release = ''
        return release

    def _check_num(self, release):
        version = release.split("(")[0]
        match = re.search(r"([0-9\.]+)", version)
        mainver = match.group(1).split(".")[0] if match else None
        return mainver

    def _check(self, release, pattern):
        return True if re.search(pattern, release) else False

    def _check_rhl(self, release):
        return self._check(release, "Red Hat Linux") and not self._check(release, "Advanced")

    def _check_rhel(self, release):
        return self._check(release, "(Enterprise|Advanced|CentOS)")

    def _check_fedora(self, release):
        return self._check(release, "Fedora")

    def dist(self):
        """
        Determine the value of the rpm 'dist' tag for this host. Adapted from the
        redhat-rpm-config package dist.sh script.
        """
        release = self._redhat_release()
        distnum = self._check_num(release)
        if distnum:
            if self._check_fedora(release):
                disttype = "fc"
            elif self._check_rhel(release):
                disttype = "el"
            elif self._check_rhl(release):
                disttype = "rhl"
            else:
                disttype = None
        if distnum and disttype:
            dist = ".%s%s" % (disttype, distnum)
        else:
            dist = ""
        return dist

    def arch(self):
        return os.uname()[4]

    def kversion(self):
        return os.uname()[2].replace('-','_')

    def afsversion(self, DIST):
        """
        Look up the OpenAFS version number from the rpm filename.
        """
        _info("Looking for afs version in %s" % (DIST))
        for rpm in glob.glob("%s/openafs-*.rpm" % (DIST)):
            match = re.search(r"/openafs-(\d+\.\d+\.\d+)-.*.rpm$", rpm)
            if match:
                afsversion = match.group(1)
                break
        if not afsversion:
            raise AssertionError("rpm version not found in DIST: %s" % (DIST))
        _info("Found rpm version: %s" % (afsversion))
        return afsversion

    def afsrel(self, DIST):
        """
        Look up the OpenAFS RPM release number from the rpm filename.
        """
        _info("Looking for afs rel in %s" % (DIST))
        for rpm in glob.glob("%s/openafs-*.rpm" % (DIST)):
            match = re.search(r"/openafs-\d+\.\d+\.\d+-([^.]+).*.rpm$", rpm)
            if match:
                afsrel = match.group(1)
                break
        if not afsrel:
            raise AssertionError("rpm rel not found in DIST: %s" % (DIST))
        _info("Found rpm rel: %s" % (afsrel))
        return afsrel


class _RpmInstall:
    """
    Installation keywords for RPM distributions.
    """
    def __init__(self, DIST):
        rpm = _RpmInfo()
        self.DIST = DIST
        self.dist = rpm.dist()
        self.arch = rpm.arch()
        self.kversion = rpm.kversion()
        self.afsversion = rpm.afsversion(DIST)
        self.afsrel = rpm.afsrel(DIST)

    def _rpm_install(self, package_files):
        """ Install the packages files. """
        assert(isinstance(package_files,list))
        _sudo("rpm -v --install --replacepkgs %s" % (" ".join(package_files)))

    def _rpm_remove(self, packages):
        """ Remove the packages. """
        assert(isinstance(packages,list))
        _sudo("rpm -v -e %s" % (" ".join(packages)))

    def _remove_openafs_packages(self):
        """ Remove remaining openafs packages, if any. """
        output = _run("rpm -qa '*openafs*'")
        if output:
            packages = output.splitlines()
            self._rpm_remove(packages)

    def _package_file(self, name):
        return "%s/%s-%s-%s%s.%s.rpm" % \
            (self.DIST, name, self.afsversion, self.afsrel, self.dist, self.arch)

    def _kmod_package_file(self):
        return "%s/kmod-openafs-%s-%s.%s.rpm" % \
            (self.DIST, self.afsversion, self.afsrel, self.kversion)

    def openafs_client_is_installed(self):
        _run("rpm -q openafs-client")

    def install_openafs_client(self):
        _info("Installing OpenAFS client packages")
        openafs        = self._package_file("openafs")
        openafs_krb5   = self._package_file("openafs-krb5")
        openafs_client = self._package_file("openafs-client")
        kmod_openafs   = self._kmod_package_file()
        self._rpm_install([openafs, openafs_krb5, openafs_client, kmod_openafs])

    def remove_openafs_client(self):
        self._rpm_remove(["openafs-client", "kmod-openafs"])
        try:
            self.openafs_server_is_installed()
        except:
            # server is not installed, so remove any remaining packages
            self._remove_openafs_packages()

    def openafs_server_is_installed(self):
        _run("rpm -q openafs-server")

    def install_openafs_server(self):
        _info("Installing OpenAFS server packages")
        openafs        = self._package_file("openafs")
        openafs_krb5   = self._package_file("openafs-krb5")
        openafs_server = self._package_file("openafs-server")
        self._rpm_install([openafs, openafs_krb5, openafs_server])

    def remove_openafs_server(self):
        self._rpm_remove(["openafs-server"])
        try:
            self.openafs_client_is_installed()
        except:
            # client is not installed, so remove any remaining packages
            self._remove_openafs_packages()

if __name__ == '__main__':
    _DEBUG = True
    i = Install()
    i.installation_setup(sys.argv[1])
    i.openafs_client_is_not_installed()
    i.openafs_server_is_not_installed()
    i.install_openafs_client()
    i.install_openafs_server()
    i.openafs_client_is_installed()
    i.openafs_server_is_installed()
    i.remove_openafs_client()
    i.remove_openafs_server()
    i.openafs_client_is_not_installed()
    i.openafs_server_is_not_installed()


