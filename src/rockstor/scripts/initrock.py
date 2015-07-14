"""
Copyright (c) 2012-2014 RockStor, Inc. <http://rockstor.com>
This file is part of RockStor.

RockStor is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published
by the Free Software Foundation; either version 2 of the License,
or (at your option) any later version.

RockStor is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
"""

import os
import shutil
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
from system.osi import run_command
import logging
import sys
import re
import time
from django.conf import settings


SYSCTL = '/usr/bin/systemctl'
BASE_DIR = settings.ROOT_DIR
BASE_BIN = '%s/bin' % BASE_DIR
DJANGO = '%s/django' % BASE_BIN
STAMP = '%s/.initrock' % BASE_DIR
FLASH_OPTIMIZE = '%s/flash-optimize' % BASE_BIN
PREP_DB = '%s/prep_db' % BASE_BIN
SUPERCTL = '%s/supervisorctl' % BASE_BIN
OPENSSL = '/usr/bin/openssl'
GRUBBY = '/usr/sbin/grubby'


def update_issue():
    default_if = None
    ipaddr = None
    o, e, c = run_command(['/usr/sbin/route'])
    for i in o:
        if (re.match('default', i) is not None):
            default_if = i.split()[-1]
    if (default_if is not None):
        o2, e, c = run_command(['/usr/sbin/ifconfig', default_if])
        for i2 in o2:
            if (re.match('inet ', i2.strip()) is not None):
                ipaddr = i2.split()[1]
    with open('/etc/issue', 'w') as ifo:
        if (ipaddr is None):
            ifo.write('The system does not have an ip address.\n\n')
            ifo.write('Rockstor cannot be configured using the web-ui '
                      'without an ip address.\n\n')
            ifo.write('Login as root and configure your network to proceed '
                      'further.\n')
        else:
            ifo.write('\nRockstor is successfully installed.\n\n')
            ifo.write('You can access the web-ui by pointing your browser to '
                      'https://%s\n\n' % ipaddr)


def set_def_kernel(logger, version=settings.SUPPORTED_KERNEL_VERSION):
    supported_kernel_path = ('/boot/vmlinuz-%s' % version)
    if (not os.path.isfile(supported_kernel_path)):
        return logger.error('Supported kernel(%s) does not exist' %
                            supported_kernel_path)
    try:
        o, e, rc = run_command([GRUBBY, '--default-kernel'])
        if (o[0] == supported_kernel_path):
            return logging.info('Supported kernel(%s) is already the default' %
                                supported_kernel_path)
    except Exception, e:
        logger.error('Exception while listing the default kernel')
        return logger.exception(e)

    try:
        run_command([GRUBBY, '--set-default=%s' % supported_kernel_path])
        return logger.info('Default kernel set to %s' % supported_kernel_path)
    except Exception, e:
        logger.error('Exception while setting kernel(%s) as default' % version)
        return logger.exception(e)


def main():
    loglevel = logging.INFO
    if (len(sys.argv) > 1 and sys.argv[1] == '-x'):
        loglevel = logging.DEBUG
    logging.basicConfig(format='%(asctime)s: %(message)s', level=loglevel)
    set_def_kernel(logging)
    shutil.copyfile('/etc/issue', '/etc/issue.rockstor')
    for i in range(30):
        try:
            update_issue()
            break
        except Exception, e:
            logging.info('exception occured while running update_issue. '
                         'Perhaps rc.local ran before it should have. '
                         'Trying again after 2 seconds')
            if (i > 28):
                logging.info('Waited too long and tried too many times. '
                             'Quiting.')
                raise e
            time.sleep(2)
    cert_loc = '%s/certs/' % BASE_DIR
    if (os.path.isdir(cert_loc)):
        if (not os.path.isfile('%s/rockstor.cert' % cert_loc) or
            not os.path.isfile('%s/rockstor.key' % cert_loc)):
            shutil.rmtree(cert_loc)

    if (not os.path.isdir(cert_loc)):
        os.mkdir(cert_loc)
        dn = ("/C=US/ST=Rockstor user's state/L=Rockstor user's "
              "city/O=Rockstor user/OU=Rockstor dept/CN=rockstor.user")
        logging.info('Creating openssl cert...')
        run_command([OPENSSL, 'req', '-nodes', '-newkey', 'rsa:2048',
                     '-keyout', '%s/first.key' % cert_loc, '-out',
                     '%s/rockstor.csr' % cert_loc, '-subj', dn])
        logging.debug('openssl cert created')
        logging.info('Creating rockstor key...')
        run_command([OPENSSL, 'rsa', '-in', '%s/first.key' % cert_loc, '-out',
                     '%s/rockstor.key' % cert_loc])
        logging.debug('rockstor key created')
        logging.info('Singing cert with rockstor key...')
        run_command([OPENSSL, 'x509', '-in', '%s/rockstor.csr' % cert_loc,
                     '-out', '%s/rockstor.cert' % cert_loc, '-req', '-signkey',
                     '%s/rockstor.key' % cert_loc, '-days', '3650'])
        logging.debug('cert signed.')
        logging.info('restarting nginx...')
        run_command([SUPERCTL, 'restart', 'nginx'])

    with open('/etc/rc.d/rc.local', 'a+') as lfo:
        found = False
        initrock_loc = '%s/initrock' % BASE_BIN
        for l in lfo.readlines():
            if (re.match(initrock_loc, l) is not None):
                found = True
        if (not found):
            lfo.write('#rockstor script. dont remove\n')
            lfo.write('%s -x\n' % initrock_loc)
    run_command(['/usr/bin/chmod', 'a+x', '/etc/rc.d/rc.local'])

    run_command([FLASH_OPTIMIZE, '-x'])
    if (os.path.isfile(STAMP)):
        return logging.info(
            'initrock ran successfully before, so not running it again.'
            ' Running it again can destroy your Rockstor state. If you know '
            'what you are doing, remove %s/.initrock '
            'and run again.' % BASE_DIR)
    logging.info('Please be patient. This script could take a few minutes')
    shutil.copyfile('%s/conf/django-hack' % BASE_DIR,
                    '%s/django' % BASE_BIN)
    run_command([SYSCTL, 'enable', 'postgresql'])
    logging.debug('Progresql enabled')
    shutil.rmtree('/var/lib/pgsql/data')
    logging.info('initializing Postgresql...')
    run_command(['/usr/bin/postgresql-setup', 'initdb'])
    logging.info('Done.')
    run_command([SYSCTL, 'restart', 'postgresql'])
    run_command([SYSCTL, 'status', 'postgresql'])
    logging.debug('Postgresql restarted')
    logging.info('Creating app databases...')
    run_command(['su', '-', 'postgres', '-c', '/usr/bin/createdb smartdb'])
    logging.debug('smartdb created')
    run_command(['su', '-', 'postgres', '-c',
                 '/usr/bin/createdb storageadmin'])
    logging.debug('storageadmin created')
    logging.info('Done')
    logging.info('Initializing app databases...')
    run_command(['su', '-', 'postgres', '-c', "psql -c \"CREATE ROLE rocky WITH SUPERUSER LOGIN PASSWORD 'rocky'\""])
    logging.debug('rocky ROLE created')
    run_command(['su', '-', 'postgres', '-c', "psql storageadmin -f /opt/rockstor/conf/storageadmin.sql.in"])
    logging.debug('storageadmin app database loaded')
    run_command(['su', '-', 'postgres', '-c', "psql smartdb -f /opt/rockstor/conf/smartdb.sql.in"])
    logging.debug('smartdb app database loaded')
    run_command(['su', '-', 'postgres', '-c', "psql storageadmin -c \"select setval('south_migrationhistory_id_seq', (select max(id) from south_migrationhistory))\""])
    logging.debug('storageadmin migration history copied')
    run_command(['su', '-', 'postgres', '-c', "psql smartdb -c \"select setval('south_migrationhistory_id_seq', (select max(id) from south_migrationhistory))\""])
    logging.debug('smartdb migration history copied')
    logging.info('Done')
    run_command(['cp', '-f', '/opt/rockstor/conf/postgresql.conf',
                 '/var/lib/pgsql/data/'])
    logging.debug('postgresql.conf copied')
    run_command(['cp', '-f', '/opt/rockstor/conf/pg_hba.conf',
                 '/var/lib/pgsql/data/'])
    logging.debug('pg_hba.conf copied')
    run_command([SYSCTL, 'restart', 'postgresql'])
    logging.info('Postgresql restarted')
    logging.info('Running app database migrations...')
    run_command([DJANGO, 'migrate', 'oauth2_provider', '--database=default',
                 '--noinput'])
    run_command([DJANGO, 'migrate', 'storageadmin', '--database=default',
                 '--noinput'])
    logging.debug('storageadmin migrated')
    run_command([DJANGO, 'migrate', 'django_ztask', '--database=default',
                 '--noinput'])
    logging.debug('django_ztask migrated')
    run_command([DJANGO, 'migrate', 'smart_manager',
                 '--database=smart_manager', '--noinput'])
    logging.debug('smart manager migrated')
    logging.info('Done')
    logging.info('Running prepdb...')
    run_command([PREP_DB, ])
    logging.info('Done')
    shutil.copy('%s/conf/rockstor.service' % BASE_DIR, '/etc/systemd/system/')
    run_command([SYSCTL, 'enable', 'rockstor'])
    run_command([SYSCTL, 'start', 'rockstor'])
    logging.info('Started rockstor service')
    logging.info('Shutting down firewall...')
    run_command([SYSCTL, 'stop', 'firewalld'])
    run_command([SYSCTL, 'disable', 'firewalld'])
    run_command(['touch', STAMP])
    logging.info('Done')
    logging.info('All set. Go to the web-ui now and start using Rockstor!')

if __name__ == '__main__':
    main()