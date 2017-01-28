#!/usr/bin/env python3
import json
import os

import cherrypy
from oic.exception import MessageException
from oic.federation import MetadataStatement
from oic.federation.bundle import get_bundle
from oic.federation.bundle import get_signing_keys
from oic.utils import webfinger
from oic.utils.jwt import JWT

from oidctest.cp.op import Provider
from oidctest.cp.op import WebFinger
from oidctest.cp.op_handler import OPHandler
from otest.flow import Flow
from otest.prof_util import SimpleProfileHandler
from src.oidctest.cp.setup import cb_setup

KEYDEFS = [
    {"type": "RSA", "key": '', "use": ["sig"]},
    {"type": "EC", "crv": "P-256", "use": ["sig"]}
]


class Sign(object):
    def __init__(self, sign_keys, iss):
        self.sign_keys = sign_keys
        self.iss = iss

    @cherrypy.expose
    def index(self, mds):
        _mds = MetadataStatement(**json.loads(mds))
        try:
            _mds.verify()
        except MessageException as err:
            raise cherrypy.CherryPyException()
        else:
            _jwt = JWT(self.sign_keys, lifetime=3600, iss=self.iss)
            jws = _jwt.pack(data=_mds)
            cherrypy.response.headers['Content-Type'] = 'application/jwt'
            return jws


class FoKeys(object):
    def __init__(self, sign_keys):
        self.sign_keys = sign_keys

    @cherrypy.expose
    def index(self, mds):
        pass


if __name__ == '__main__':
    import argparse
    from oidctest.rp import provider

    parser = argparse.ArgumentParser()
    parser.add_argument('-b', dest='bundle', required=True)
    parser.add_argument('-d', dest='debug', action='store_true')
    parser.add_argument('-f', dest='flowsdir', required=True)
    parser.add_argument('-i', dest='iss', required=True)
    parser.add_argument('-k', dest='insecure', action='store_true')
    parser.add_argument('-p', dest='port', default=80, type=int)
    parser.add_argument('-P', dest='path')
    parser.add_argument('-s', dest='sign_key', required=True)
    parser.add_argument('-t', dest='tls', action='store_true')
    parser.add_argument(dest="config")
    args = parser.parse_args()

    _com_args, _op_arg, config = cb_setup(args)

    sign_key = get_signing_keys(args.iss, KEYDEFS, args.sign_key)
    jb = get_bundle(args.iss, config.FOS, sign_key, args.bundle,
                    config.KEYDEFS, config.BASE_PATH)

    op_handler = OPHandler(provider.Provider, _op_arg, _com_args, config)
    _flows = Flow(args.flowsdir, profile_handler=SimpleProfileHandler)

    cherrypy.tree.mount(Sign(sign_key, args.iss), '/sign')
    cherrypy.tree.mount(FoKeys(jb), '/fokeys')
    cherrypy.tree.mount(WebFinger(webfinger.WebFinger()),
                        '/.well-known/webfinger')
    cherrypy.tree.mount(Provider(op_handler, _flows), '/')

    cherrypy.engine.start()
    cherrypy.engine.block()