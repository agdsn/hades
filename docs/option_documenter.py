import sphinx.ext.autodoc

from hades.config.base import Option


class OptionDocumenter(sphinx.ext.autodoc.ClassDocumenter):
    priority = 10
    objtype = 'option'

    @classmethod
    def can_document_member(cls, member, membername, isattr, parent):
        # type: (Any, unicode, bool, Any) -> bool
        return isinstance(member, type) and issubclass(member, Option)



def setup(app):
    pass
