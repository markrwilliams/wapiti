# -*- coding: utf-8 -*-
"""
    wapiti.operations.models
    ~~~~~~~~~~~~~~~~~~~~~~~~

    This module provides structures and abstractions for creating
    consistent Operation interfaces, regardless of underlying
    Mediawiki API response types.

    For example the ``prop=revisions`` and ``list=usercontribs`` APIs
    both return lists of revision information, however not all of the
    attributes afforded by ``prop=revisions`` are available from
    ``list=usercontribs``. Wapiti models and operations strive to
    resolve and abstract this fact away from the user as sanely as
    possible.
"""
from __future__ import unicode_literals

from datetime import datetime
from collections import namedtuple, OrderedDict


def parse_timestamp(timestamp):
    return datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')


LanguageLink = namedtuple('LanguageLink', 'url language origin_page')
InterwikiLink = namedtuple('InterwikiLink', 'url prefix origin_page')
ExternalLink = namedtuple('ExternalLink', 'url origin_page')

NamespaceDescriptor = namedtuple('NamespaceDescriptor', 'id title canonical')
InterwikiDescriptor = namedtuple('InterwikiDescriptor', 'alias url language')


_MISSING = object()


class WapitiModelAttr(object):
    def __init__(self, name, **kw):
        self.name = name
        self.mw_name = kw.pop('mw_name', name)
        self.display = kw.pop('display', False)
        try:
            self.default = kw.pop('default')
        except KeyError:
            self.default = _MISSING
        if kw:
            raise ValueError('got unexpected keyword arguments: %r'
                             % kw.keys())

    def __repr__(self):
        ret = [self.__class__.__name__, '(', repr(self.name)]
        if self.mw_name != self.name:
            ret.extend([', mw_name=', repr(self.mw_name)])
        if self.default is not _MISSING:
            ret.extend([', default=', repr(self.default)])
        if self.display:
            ret.extend([', display=', repr(self.display)])
        ret.append(')')
        return ''.join(ret)

    def __iter__(self):
        return iter((self.name, self.mw_name, self.default, self.display))


WMA = WapitiModelAttr  # Windows Media Audio


def title_talk2subject(title):
    talk_pref, _, title_suf = title.partition(':')
    subj_pref, _, _ = talk_pref.rpartition('talk')
    subj_pref = subj_pref.strip()
    new_title = subj_pref + ':' + title_suf
    new_title = new_title.lstrip(':')
    return new_title


def title_subject2talk(title):
    subj_pref, _, title_suf = title.partition(':')
    subj_pref = subj_pref.strip()
    if not subj_pref:
        talk_pref = 'Talk'
    elif subj_pref.endswith('talk'):
        talk_pref = subj_pref
    else:
        talk_pref = subj_pref + ' talk'
    new_title = talk_pref + ':' + title_suf
    return new_title


class WapitiModelMeta(type):
    """
    The foundation of Wapiti's data models, which attempt to add
    consistency and order to the wide variety of return types used
    across different Mediawiki APIs. This metaclass enables certain
    inheritance-like usage patterns in models. See WapitiModelBase's
    docstring for more information.

    The `attributes` dictionary is a mapping of Python class attribute
    names to Mediawiki API result keys (e.g., `pageid` becomes
    `page_id` on the Python object).

    The `defaults` dictionary is a mapping of Python attribute name to
    default value, if allowed. If an attribute does not have a default
    value, and is missing upon instantiation of a model, an exception
    will be raised.
    """
    attributes = []

    def __new__(cls, name, bases, attrs):
        all_attributes = OrderedDict()
        for base in bases:
            base_attr_list = getattr(base, 'attributes', [])
            base_attr_dict = OrderedDict([(a.name, a) for a in base_attr_list])
            all_attributes.update(base_attr_dict)
        attr_dict = OrderedDict([(a.name, a) for a
                                 in attrs.get('attributes', [])])
        all_attributes.update(attr_dict)
        attrs['attributes'] = all_attributes.values()
        ret = super(WapitiModelMeta, cls).__new__(cls, name, bases, attrs)
        return ret


class WapitiModelBase(object):
    """
    The more-concrete counterpart of WapitiModelMeta, which primarily
    provides initialization logic.

    There are two methods for instantiation, the standard
    ``__init__()`` (e.g., ``CategoryInfo()``), which takes attributes
    as keyword arguments, and ``from_query()``, which usually takes a
    dictionary deserialized from JSON, as returned by Mediawiki
    API. For information on `attributes` and `defaults`, see
    WapitiModelMeta.
    """

    __metaclass__ = WapitiModelMeta
    attributes = []

    def __init__(self, **kw):
        missing = []
        for attr in self.attributes:
            try:
                val = kw.pop(attr.name)
            except KeyError:
                if attr.default is _MISSING:
                    missing.append(attr.name)
                    continue
                val = attr.default
            setattr(self, attr.name, val)
        if missing:
            import pdb;pdb.set_trace()
            raise ValueError('missing expected keyword arguments: %r'
                             % missing)
        # TODO: raise on unexpected keyword arguments?
        return

    @classmethod
    def from_query(cls, q_dict, **kw):
        kwargs = {}
        all_q_dict = dict(kw)
        all_q_dict.update(q_dict)
        for name, mw_name, _, _ in cls.attributes:
            if mw_name is None:
                continue
            try:
                kwargs[name] = all_q_dict[mw_name]
            except KeyError:
                pass
        return cls(**kwargs)


class PageIdentifier(WapitiModelBase):
    attributes = [WMA('title', display=True),
                  WMA('page_id', mw_name='pageid', display=True),
                  WMA('ns', display=True),
                  WMA('source')]

    @property
    def is_subject_page(self):
        return (self.ns >= 0 and self.ns % 2 == 0)

    @property
    def is_talk_page(self):
        return (self.ns >= 0 and self.ns % 2 == 1)

    def _to_string(self, raise_exc=False):
        try:
            class_name = self.__class__.__name__
            return (u'%s(%r, %r, %r, %r)'
                    % (class_name,
                       self.title,
                       self.page_id,
                       self.ns,
                       self.source))
        except AttributeError:
            if raise_exc:
                raise
            return super(PageIdentifier, self).__str__()

    def __str__(self):
        return self._to_string()

    def __repr__(self):
        try:
            return self._to_string(raise_exc=True)
        except:
            return super(PageIdentifier, self).__repr__()


class PageInfo(PageIdentifier):
    attributes = [WMA('subject_id', mw_name='subjectid', default=None),
                  WMA('talk_id', mw_name='talkid', default=None)]

    def __init__(self, **kw):
        req_title = kw.pop('req_title', None)
        super(PageInfo, self).__init__(**kw)
        self.req_title = req_title or self.title

        if self.is_subject_page:
            self.subject_id = self.page_id
        elif self.is_talk_page:
            self.talk_id = self.page_id
        else:
            raise ValueError('special or nonexistent namespace: %r' % self.ns)

    def get_subject_info(self):
        if self.is_subject_page:
            return self
        if self.subject_id is None:
            raise ValueError('subject_id not set')
        subj_title = title_talk2subject(self.title)
        subj_ns = self.ns - 1
        kwargs = dict(self.__dict__)
        kwargs['title'] = subj_title
        kwargs['ns'] = subj_ns
        return PageInfo(**kwargs)

    def get_talk_info(self):
        if self.is_talk_page:
            return self
        if self.talk_id is None:
            raise ValueError('talk_id not set')
        talk_title = title_subject2talk(self.title)
        talk_ns = self.ns + 1
        kwargs = dict(self.__dict__)
        kwargs['title'] = talk_title
        kwargs['ns'] = talk_ns
        return PageInfo(**kwargs)


class CategoryInfo(PageInfo):
    attributes = [WMA('total_count', mw_name='size', default=0, display=True),
                  WMA('page_count', mw_name='pages', default=0),
                  WMA('file_count', mw_name='files', default=0),
                  WMA('subcat_count', mw_name='subcats', default=0, display=True)]


class RevisionInfo(PageInfo):
    attributes = [WMA('rev_id', mw_name='revid', display=True),
                  WMA('size'),
                  WMA('user_text', mw_name='user', default='!userhidden'),
                  WMA('user_id', mw_name='userid', default=-1),
                  WMA('timestamp', display=True),
                  WMA('comment', default=''),
                  WMA('parsed_comment', mw_name='parsedcomment', default=''),
                  WMA('tags')]

    # note that certain revisions may have hidden the fields
    # user_id, user_text, and comment for administrative reasons,
    # aka "oversighting"
    # TODO: is oversighting better handled in operation?

    def __init__(self, *a, **kw):
        super(RevisionInfo, self).__init__(*a, **kw)
        self.timestamp = parse_timestamp(self.timestamp)


class Revision(RevisionInfo):
    attributes = [WMA('parent_rev_id', mw_name='parentid', display=True),
                  WMA('content', mw_name='*', default=''),  # default=''?
                  WMA('is_parsed')]


class ImageInfo(PageIdentifier):
    attributes = [WMA('image_repo', mw_name='imagerepository'),
                  WMA('missing', default=False),
                  WMA('url', default=''),  # will only exist if non-local repo
                  WMA('dimensions', default=''),
                  WMA('mime', default=''),
                  WMA('thumbmime', default=''),
                  WMA('media_type', mw_name='mediatype', default=''),
                  WMA('metadata', default=''),
                  WMA('archive_name', mw_name='archivename', default=''),
                  WMA('bitdepth', default='')]


#
# Protections
#
NEW = 'NEW'
AUTOCONFIRMED = 'AUTOCONFIRMED'
SYSOP = 'SYSOP'
PROTECTION_ACTIONS = ('create', 'edit', 'move', 'upload')


Protection = namedtuple('Protection', 'level, expiry')


class ProtectionInfo(object):
    # TODO: turn into mixin, add to PageIdentifier
    """
    For more info on protection,
    see https://en.wikipedia.org/wiki/Wikipedia:Protection_policy
    """
    levels = {
        'new': NEW,
        'autoconfirmed': AUTOCONFIRMED,
        'sysop': SYSOP,
    }

    def __init__(self, protections, page_ident=None):
        self.page_ident = page_ident

        protections = protections or {}
        self.protections = {}
        for p in protections:
            if not p['expiry'] == 'infinity':
                expiry = parse_timestamp(p['expiry'])
            else:
                expiry = 'infinity'
            level = self.levels[p['level']]
            self.protections[p['type']] = Protection(level, expiry)

    @property
    def has_protection(self):
        return any([x.level != NEW for x in self.protections.values()])

    @property
    def has_indef(self):
        return any([x.expiry == 'infinity' for x in self.protections.values()])

    @property
    def is_full_prot(self):
        try:
            if self.protections['edit'].level == SYSOP and \
                    self.protections['move'].level == SYSOP:
                return True
            else:
                return False
        except (KeyError, AttributeError):
            return False

    @property
    def is_semi_prot(self):
        try:
            if self.protections['edit'].level == AUTOCONFIRMED:
                return True
            else:
                return False
        except (KeyError, AttributeError):
            return False

    def __repr__(self):
        return u'ProtectionInfo(%r)' % self.protections


class CoordinateIndentifier(object):
    def __init__(self, coord, page_ident=None):
        self.page_ident = page_ident
        self.lat = coord.get('lat')
        self.lon = coord.get('lon')
        self.type = coord.get('type')
        self.name = coord.get('name')
        self.dim = coord.get('dim')
        self.country = coord.get('country')
        self.region = coord.get('region')
        if coord.get('primary', False):
            self.primary = True
        else:
            self.primary = False
        return
