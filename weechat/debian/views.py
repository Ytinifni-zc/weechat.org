# -*- coding: utf-8 -*-
#
# Copyright (C) 2003-2018 Sébastien Helleu <flashcode@flashtux.org>
#
# This file is part of WeeChat.org.
#
# WeeChat.org is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# WeeChat.org is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with WeeChat.org.  If not, see <http://www.gnu.org/licenses/>.
#

"""Views for Debian repositories."""

from datetime import datetime, timedelta
import gzip
from os import path, stat
import pytz
import re

from django.conf import settings
from django.shortcuts import render

from weechat.common.path import repo_path_join
from weechat.debian.models import Repo


def get_repository_packages(repository):
    """Get list of packages for a repository."""
    timezone = pytz.timezone(settings.TIME_ZONE)
    now = datetime.now(tz=timezone)
    repopkgs = []
    for arch in repository.arch.split(','):
        build = {
            'id': '%s_%s' % (repository.name, repository.version.version),
            'repo': repository,
            'arch': arch,
            'date': None,
            'files': [],
        }
        filename = repository.path_packages_gz(arch)
        build['date'] = stat(filename).st_mtime
        with gzip.open(filename, 'rb') as _file:
            pkg = {}
            for line in _file.readlines():
                line = line.strip().decode('utf-8')
                if len(line) == 0:
                    if pkg:
                        pkg['repoarch'] = '%s_%s' % (
                            repository.name,
                            repository.version.codename,
                        )
                        pkg['repo'] = repository
                        pkg['distro'] = repository.name
                        pkg['arch'] = arch
                        pkgfilename = repo_path_join(repository.domain,
                                                     pkg['Filename'])
                        fstat = stat(pkgfilename)
                        pkg['size'] = fstat.st_size
                        date_time = datetime.fromtimestamp(fstat.st_mtime,
                                                           tz=timezone)
                        pkg['builddatetime'] = date_time
                        add_hours = repository.build_frequency
                        if repository.active and add_hours > 0:
                            nextbuilddatetime = (date_time +
                                                 timedelta(hours=add_hours))
                            if nextbuilddatetime > now:
                                pkg['nextbuilddatetime'] = nextbuilddatetime
                        pkg['basename'] = path.basename(pkg['Filename'])
                        pkg['anchor'] = '%s_%s_%s_%s' % (
                            repository.name,
                            repository.version.codename,
                            pkg['Version'],
                            arch,
                        )
                        if 'Source' not in pkg:
                            pkg['Source'] = pkg['Package']
                        pkg['version_type'] = ('dev'
                                               if 'dev' in pkg['Version']
                                               else 'stable')
                        repopkgs.append(pkg)
                    pkg = {}
                match = re.match('^([^ ]+): (.*)$', line)
                if match:
                    pkg[match.group(1)] = match.group(2)
    return repopkgs


def repos(request, active='active', files=''):
    """Page with debian repositories."""
    if active == 'active':
        repositories = (Repo.objects.all().filter(active=1).filter(visible=1)
                        .order_by('priority'))
    else:
        repositories = (Repo.objects.all().filter(visible=1)
                        .order_by('priority'))
    debpkgs = []
    errors = []
    for repository in repositories:
        try:
            repo_packages = get_repository_packages(repository)
            debpkgs.extend(sorted(repo_packages,
                                  key=lambda p: p['builddatetime'],
                                  reverse=True))
        except:  # noqa: E722
            errors.append('%s %s' % (repository.name, repository.version))
    return render(
        request,
        'download/debian.html',
        {
            'debpkgs': debpkgs,
            'active': active,
            'allfiles': files == 'files',
            'repositories': repositories,
            'errors': errors,
        },
    )
