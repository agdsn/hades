import collections
from functools import partial
import os
import os.path
import shutil
import sys

import jinja2
import netaddr
import pkg_resources
from hades.config.loader import get_config


class ConfigGenerator(object):
    TEMPLATE_SUFFIX = ".j2"

    def __init__(self, template_dir, config):
        self.config = config
        self.template_dir = template_dir
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.template_dir),
            auto_reload=False, autoescape=False, keep_trailing_newline=True,
            undefined=jinja2.StrictUndefined,
            extensions=['jinja2.ext.do', 'jinja2.ext.loopcontrols',
                        'jinja2.ext.with_'],
        )
        self.env.globals.update({
            'netaddr': netaddr,
        })

    def from_directory(self, name, target_dir):
        source_base = os.path.join(self.template_dir, name)
        sources = collections.deque()
        sources.append(source_base)
        while sources:
            source = sources.pop()
            relpath = os.path.relpath(source, source_base)
            target = os.path.normpath(os.path.join(target_dir, relpath))
            if os.path.isdir(source):
                sources.extend(map(partial(os.path.join, source),
                                   os.listdir(source)))
                if not os.path.exists(target):
                    os.mkdir(target)
            else:
                if source.endswith(self.TEMPLATE_SUFFIX):
                    template_name = os.path.relpath(source, self.template_dir)
                    template = self.env.get_template(template_name)
                    target = target[:-len(self.TEMPLATE_SUFFIX)]
                    with open(target, 'w', encoding='UTF-8') as f:
                        stream = template.stream(BASE_DIRECTORY=target_dir,
                                                 TARGET=target, **self.config)
                        f.writelines(stream)
                else:
                    shutil.copy(source, target)

    def from_file(self, name, output):
        target = os.path.join(self.template_dir, name)
        base_directory = os.path.dirname(target)
        stream = self.env.get_template(name).stream(
            BASE_DIRECTORY=base_directory, TARGET=target, **self.config)
        output.writelines(stream)


def write_single_file_config(generator, name, args):
    if len(args) < 3:
        generator.from_file(name, sys.stdout)
    else:
        target_file = args[2]
        with open(target_file, 'w', encoding='utf-8') as f:
            generator.from_file(name, f)
    return 0


def write_directory_config(generator, name, args):
    if len(args) < 3:
        return os.EX_USAGE
    target_dir = args[2]
    generator.from_directory(name, target_dir)
    return 0


def write_arping_config(generator, args):
    return write_single_file_config(generator, 'arping.ini.j2', args)


def write_freeradius_config(generator, args):
    return write_directory_config(generator, 'freeradius', args)


def write_iptables_config(generator, args):
    return write_single_file_config(generator, "iptables.j2", args)


def write_nginx_config(generator, args):
    return write_directory_config(generator, "nginx", args)


def write_postgresql_schema(generator, args):
    return write_single_file_config(generator, "schema.sql.j2", args)


def write_regular_dnsmasq_config(generator, args):
    return write_single_file_config(generator, "regular-dnsmasq.conf.j2", args)


def write_unauth_dnsmasq_config(generator, args):
    return write_single_file_config(generator, "unauth-dnsmasq.conf.j2", args)


def write_unbound_config(generator, args):
    return write_single_file_config(generator, "unbound.conf.j2", args)


def write_uwsgi_config(generator, args):
    return write_single_file_config(generator, "uwsgi.ini.j2", args)


commands = {
    "arping": write_arping_config,
    "freeradius": write_freeradius_config,
    "iptables": write_iptables_config,
    "nginx": write_nginx_config,
    "postgresql-schema": write_postgresql_schema,
    "regular-dnsmasq": write_regular_dnsmasq_config,
    "unauth-dnsmasq": write_unauth_dnsmasq_config,
    "unbound": write_unbound_config,
    "uwsgi": write_uwsgi_config,
}


def main(args):
    if len(args) < 2:
        return os.EX_USAGE
    config = get_config()
    template_dir = pkg_resources.resource_filename('hades.config', 'templates')
    generator = ConfigGenerator(template_dir, config)
    command = commands.get(args[1])
    if command is None:
        print("Unknown config generation command {}".format(args[1]),
              file=sys.stderr)
        return os.EX_USAGE
    return command(generator, args)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
