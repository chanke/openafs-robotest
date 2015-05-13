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
import re
import urllib
from HTMLParser import HTMLParser


class LinkHTMLParser(HTMLParser):
    """Extract link urls from an html document."""

    def __init__(self):
        HTMLParser.__init__(self)
        self.urls = []

    def handle_a_tag(self, attrs):
        """Extract the link url from an a tag.
        Ignore the link name; it is not needed for this tool.
        """
        for attr in attrs:
            if attr[0] == 'href':
                self.urls.append(attr[1])
    def handle_starttag(self, tag, attrs):
        """Handle html a tags; ignore others."""
        if tag == "a":
            self.handle_a_tag(attrs)

def retrieve_rpm_urls(version, platform, **kwargs):
    """Retrieve the list of urls for a version and platform."""
    kmod_found = False
    arch = kwargs.get('arch', os.uname()[4])
    kernel = kwargs.get('kernel', os.uname()[2]).replace('-', '_')
    site = kwargs.get('site', "http://openafs.org")

    parts = [site, 'pages', 'release', version, 'index-%s.html' % (platform)]
    index = "/".join(parts)

    message = "Getting list of URLs ..."
    spacer = "." * (64 - len(message))
    sys.stdout.write(message)
    sys.stdout.flush()
    try:
        parser = LinkHTMLParser()
        response = urllib.urlopen(index)
        for line in response:
            parser.feed(line)
    except IOError as e:
        sys.stdout.write(" [error]\n")
        raise Exception("Error retrieving urls: %s\n" % (e.message))
    urls = []
    for url in parser.urls:
        if not url.endswith(".rpm"):
            continue
        url = url.lstrip("/")
        parts = url.split("/")
        if len(parts) == 6 and parts[4] == arch:
            if parts[5].startswith('openafs-'):
                urls.append(url)
            elif parts[5].startswith('kmod-openafs-'):
                if parts[5].endswith("%s.rpm" % (kernel)):
                    kmod_found = True
                    urls.append(url)
    if urls:
        sys.stdout.write("%s [%s]\n" % (spacer, "ok"))
        if platform.startswith('rhel') and not kmod_found:
            sys.stderr.write("Warning: kmod not found for kernel version %s\n" % (kernel))
    else:
        sys.stdout.write("%s [%s]\n" % (spacer, "error"))
        sys.stderr.write("Error: No files found for version %s, platform %s\n" % (version, platform))
    return urls

def download_files(urls, **kwargs):
    """Download the files from the list of urls."""
    files = [] # list of files downloaded
    directory = kwargs.get('directory', "./site/rpms").rstrip("/")
    site = kwargs.get('site', "http://openafs.org")
    dryrun = kwargs.get('dryrun', False)

    if not os.path.isdir(directory) and urls and not dryrun:
        os.makedirs(directory)
    sys.stdout.write("Downloading to %s\n" % (directory))

    for url in urls:
        if not url.startswith("http"):
            url = "/".join([site, url])
        filename = os.path.join(directory, os.path.basename(url))
        message = "Downloading %s ..." % (os.path.basename(filename))
        sys.stdout.write(message)
        sys.stdout.flush()
        spacer = "." * (64 - len(message))
        try:
            if kwargs.get('dryrun', False):
                sys.stdout.write("%s [%s]\n" % (spacer, "skipped"))
            else:
                filename,headers = urllib.urlretrieve(url, filename)
                files.append(filename)
                sys.stdout.write("%s [%s]\n" % (spacer, "ok"))
        except IOError as e:
            sys.stdout.write("%s [%s]\n" % (spacer, "error"))
            raise Exception("Error downloading file: url=%s, error=%s\n" % (url, e.message))

    status = {'files': files}
    return status

def download(version, platform, **kwargs):
    if platform in ('rhel5', 'rhel6', 'openSUSE_12.3'):
        urls = retrieve_rpm_urls(version, platform, **kwargs)
    else:
        raise ValueError("Unexpected platform: %s" % (platform))
    return download_files(urls, **kwargs)

