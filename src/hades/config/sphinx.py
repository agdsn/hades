"""
Sphinx extension for Hades's options
"""
from typing import Any

import sphinx.ext.autodoc
from docutils.parsers.rst.roles import CustomRole, code_role
from sphinx.application import Sphinx
from sphinx.directives import ObjectDescription
from sphinx.domains import Domain, ObjType
from sphinx.roles import XRefRole
from sphinx.util.docfields import Field, GroupedField
from sphinx.util.docstrings import prepare_docstring

from hades.config.base import Compute, Option, OptionMeta, qualified_name


class OptionDirective(ObjectDescription):
    doc_field_types = [
        Field('default', label='Default'),
        Field('required', label='Required'),
        Field('static-check', label='Static Check'),
        Field('runtime-check', label='Runtime Check'),
        GroupedField('type', label='Types'),
    ]

    def add_target_and_index(self, name, sig, signode):
        targetname = self.objtype + name
        if targetname not in self.state.document.ids:
            signode['names'].append(targetname)
            signode['ids'].append(targetname)
            signode['first'] = (not self.names)
            self.state.document.note_explicit_target(signode)
            inv = self.env.domaindata[self.domain]['objects']
            if name in inv:
                self.state_machine.reporter.warning(
                    'duplicate option description of {}, other instance in {}'
                    .format(name, self.env.doc2path(inv[name][0])),
                    line=self.lineno)
            inv[name] = self.env.docname

            self.indexnode['entries'].append(('pair: option; ' + name, name,
                                              targetname, '', None))


class HadesDomain(Domain):
    name = 'hades'
    label = 'Hades'
    object_types = {
        'option': ObjType('Option', 'option'),
    }
    directives = {
        'option': OptionDirective,
    }
    roles = {
        'option': XRefRole(),
    }


class OptionDocumenter(sphinx.ext.autodoc.ClassDocumenter):
    priority = 10
    domain = HadesDomain.name
    objtype = 'option'

    @classmethod
    def can_document_member(cls, member: Any, membername: str, isattr: bool,
                            parent: Any) -> bool:
        return isinstance(member, type) and issubclass(member, Option)

    def add_field(self, name: str, body: str, sourcename: str):
        """
        Add a field list item

        :param name: Name of the field
        :param body: Body of the field, multiple lines will be indented
        :param sourcename: Source name
        """
        lines = iter(prepare_docstring(body))
        self.add_line(":{}:".format(name), sourcename)
        original_indent = self.indent
        self.indent += '   '
        for line in lines:
            self.add_line(line, sourcename)
        self.indent = original_indent
        self.add_line("", sourcename)

    def generate(self, more_content=None, real_modname=None,
                 check_module: bool = False, all_members: bool = False):
        self.parse_name()
        self.import_object()
        idx = len(self.directive.result)
        # type: OptionMeta
        option = self.object
        sourcename = self.get_sourcename()
        name = option.__name__
        self.add_line(".. hades:option:: " + name, sourcename)
        self.add_line("", sourcename)
        self.indent += self.content_indent
        self.add_content(more_content)
        self.add_line("", sourcename)
        if option.required:
            self.add_line(":required: This option is **required**.", sourcename)
            self.add_line("", sourcename)
        if option.has_default:
            self.add_field("default", (
                option.default.__doc__
                if isinstance(option.default, Compute) else
                ":python:`{!r}`".format(option.default)
            ), sourcename)
        if option.type is None:
            types = ()
        elif isinstance(option.type, tuple):
            types = option.type
        else:
            types = (option.type,)
        for t in types:
            self.add_field("type", ":class:`{}`"
                           .format(qualified_name(t)), sourcename)
        if option.static_check is not None:
            self.add_field("Static Check", option.static_check.__doc__,
                           sourcename)
        if option.runtime_check is not None:
            self.add_field("Runtime Check", option.runtime_check.__doc__,
                           sourcename)
        print('\n'.join(self.directive.result[idx:]))
        #print(self.directive.result[idx:])


def setup(app: Sphinx):
    # Define a custom role for highlighted inline code
    app.add_role("python", CustomRole(
        "python", code_role, {'language': 'python', 'class': ['highlight']}
    ))
    app.add_role("sql", CustomRole(
        "sql", code_role, {'language': 'sql', 'class': ['highlight']}
    ))
    app.add_domain(HadesDomain)
    app.add_autodocumenter(OptionDocumenter)
    return {
        'parallel_read_safe': True,
    }
